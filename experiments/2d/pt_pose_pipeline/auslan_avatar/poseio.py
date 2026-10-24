"""
Loading of .pt motion files.

The dataset ships plain numpy arrays inside a torch archive, so we can read
them without torch installed. If torch *is* available we just use it; the
fallback exists so the pipeline runs in environments (like .venv-1) that
never had torch.
"""

import codecs
import io
import pickle
import zipfile
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# torch-free unpickler
# ---------------------------------------------------------------------------

_STORAGE_DTYPES = {
    "DoubleStorage": np.float64,
    "FloatStorage": np.float32,
    "HalfStorage": np.float16,
    "LongStorage": np.int64,
    "IntStorage": np.int32,
    "ShortStorage": np.int16,
    "CharStorage": np.int8,
    "ByteStorage": np.uint8,
    "BoolStorage": np.bool_,
}


class _Opaque:
    """Stand-in for any class we do not need to reconstruct faithfully."""

    def __init__(self, module, name, *args):
        self.module = module
        self.name = name
        self.args = args
        self.state = None

    def __setstate__(self, state):
        self.state = state

    def __repr__(self):
        return f"<opaque {self.module}.{self.name}>"


class _DType:
    def __init__(self, name, *_):
        self.dtype = np.dtype(name)

    def __setstate__(self, state):
        # numpy dtype state: (version, byteorder, ...)
        if len(state) > 1 and state[1] in "<>|=":
            self.dtype = self.dtype.newbyteorder(state[1])


class _NDArray:
    """numpy.core.multiarray._reconstruct placeholder."""

    def __init__(self):
        self.state = None

    def __setstate__(self, state):
        self.state = state

    def to_numpy(self):
        _version, shape, dtype, _fortran, data = self.state
        dtype = dtype.dtype if isinstance(dtype, _DType) else np.dtype(dtype)
        if isinstance(data, (bytes, bytearray)):
            array = np.frombuffer(data, dtype=dtype)
        else:
            array = np.array(data, dtype=dtype)
        return array.reshape(shape).copy()


class _StorageRef:
    def __init__(self, key, dtype, numel):
        self.key = key
        self.dtype = dtype
        self.numel = numel
        self.array = None


class _TorchlessUnpickler(pickle.Unpickler):
    def __init__(self, buf, archive, prefix):
        super().__init__(buf)
        self._archive = archive
        self._prefix = prefix

    def find_class(self, module, name):
        if module == "_codecs" and name == "encode":
            return codecs.encode
        if module.startswith("numpy") and name == "dtype":
            return _DType
        if name == "_reconstruct":
            return lambda *a, **k: _NDArray()
        if name == "_rebuild_tensor_v2":
            return _rebuild_tensor_v2
        if name == "OrderedDict":
            return dict
        return lambda *a, **k: _Opaque(module, name, *a)

    def persistent_load(self, pid):
        # ("storage", storage_type, key, location, numel)
        if not (isinstance(pid, tuple) and pid and pid[0] == "storage"):
            return None
        _, storage_type, key, _location, numel = pid
        name = getattr(storage_type, "name", None) or getattr(
            storage_type, "__name__", ""
        )
        dtype = _STORAGE_DTYPES.get(name, np.float32)
        ref = _StorageRef(str(key), dtype, numel)
        for candidate in (
            f"{self._prefix}/data/{ref.key}",
            f"{self._prefix}/{ref.key}",
        ):
            if candidate in self._archive.namelist():
                raw = self._archive.read(candidate)
                ref.array = np.frombuffer(raw, dtype=dtype)
                break
        return ref


def _rebuild_tensor_v2(storage, storage_offset, size, stride, *_args, **_kwargs):
    if not isinstance(storage, _StorageRef) or storage.array is None:
        return np.zeros(tuple(size), dtype=np.float32)
    flat = storage.array
    size = tuple(int(s) for s in size)
    if not size:
        return flat[storage_offset]
    stride = tuple(int(s) for s in stride)
    itemsize = flat.dtype.itemsize
    view = np.lib.stride_tricks.as_strided(
        flat[storage_offset:],
        shape=size,
        strides=tuple(s * itemsize for s in stride),
    )
    return np.ascontiguousarray(view)


def _materialise(obj):
    """Recursively turn placeholder arrays into real numpy arrays."""
    if isinstance(obj, _NDArray):
        return obj.to_numpy()
    if isinstance(obj, _StorageRef):
        return obj.array
    if isinstance(obj, dict):
        return {k: _materialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        built = [_materialise(v) for v in obj]
        return type(obj)(built) if not isinstance(obj, tuple) else tuple(built)
    return obj


def load_pt(path):
    """Load a .pt file into plain Python/numpy objects."""
    try:
        import torch  # noqa: F401

        import torch as _torch

        data = _torch.load(path, map_location="cpu", weights_only=False)
        return _detorch(data)
    except ImportError:
        pass

    with zipfile.ZipFile(path) as archive:
        pkl_name = next(
            n for n in archive.namelist() if n.endswith("data.pkl")
        )
        prefix = pkl_name.rsplit("/", 1)[0] if "/" in pkl_name else ""
        raw = archive.read(pkl_name)
        unpickler = _TorchlessUnpickler(io.BytesIO(raw), archive, prefix)
        return _materialise(unpickler.load())


def _detorch(obj):
    """Convert torch tensors to numpy, recursively."""
    import torch

    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().numpy()
    if isinstance(obj, dict):
        return {k: _detorch(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        built = [_detorch(v) for v in obj]
        return tuple(built) if isinstance(obj, tuple) else built
    return obj


# ---------------------------------------------------------------------------
# clip extraction
# ---------------------------------------------------------------------------


@dataclass
class PoseClip:
    """One sign's raw keypoint motion."""

    name: str
    kps: np.ndarray  # (frames, joints, 3) -> x, y, confidence
    fps: float = 25.0
    meta: dict = field(default_factory=dict)

    def __len__(self):
        return int(self.kps.shape[0])

    @property
    def n_joints(self):
        return int(self.kps.shape[1])

    @property
    def duration(self):
        return len(self) / self.fps


def _find_kps(obj, depth=0):
    """Find the keypoint array in whatever shape the file happens to be."""
    if depth > 6:
        return None
    if isinstance(obj, np.ndarray):
        if obj.ndim == 3 and obj.shape[-1] in (2, 3) and obj.shape[1] >= 17:
            return obj
        return None
    if isinstance(obj, dict):
        # prefer the documented location
        for key in ("KPS", "kps", "keypoints", "pose", "motion"):
            if key in obj:
                found = _find_kps(obj[key], depth + 1)
                if found is not None:
                    return found
        for key in ("Signer", "Annotation", "annotation", "data"):
            if key in obj:
                found = _find_kps(obj[key], depth + 1)
                if found is not None:
                    return found
        for value in obj.values():
            found = _find_kps(value, depth + 1)
            if found is not None:
                return found
    if isinstance(obj, (list, tuple)):
        for value in obj:
            found = _find_kps(value, depth + 1)
            if found is not None:
                return found
    return None


def read_clip(path, clip_key=None, fps=25.0, name=None):
    """
    Read a single sign clip from a .pt file.

    Accepts the dataset layout ({clip: {Annotation: {Signer: {KPS}}}}), a
    single-clip dict, or a bare (frames, joints, 3) array.
    """
    data = load_pt(path)

    if clip_key is not None:
        if clip_key not in data:
            raise KeyError(
                f"{path}: clip {clip_key!r} not found; have {list(data)[:8]}"
            )
        data = data[clip_key]

    kps = _find_kps(data)
    if kps is None:
        raise ValueError(f"{path}: no (frames, joints, 2|3) keypoint array found")

    kps = np.asarray(kps, dtype=np.float64)
    if kps.shape[-1] == 2:  # no confidence channel -> assume all valid
        ones = np.ones(kps.shape[:-1] + (1,))
        kps = np.concatenate([kps, ones], axis=-1)

    meta = {}
    if isinstance(data, dict):
        meta = {k: v for k, v in data.items() if isinstance(v, (str, int, float))}

    return PoseClip(
        name=name or (meta.get("Name") or str(path)),
        kps=kps,
        fps=fps,
        meta=meta,
    )


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def save_pt(obj, path):
    """
    Write `obj` as a torch-loadable .pt file.

    Uses torch when present. Otherwise it writes the same container torch
    produces for pure-numpy payloads: a zip holding `archive/data.pkl`
    (protocol-2 pickle) and `archive/version`.
    """
    try:
        import torch

        torch.save(obj, path)
        return path
    except ImportError:
        pass

    payload = pickle.dumps(obj, protocol=2)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("archive/data.pkl", payload)
        archive.writestr("archive/version", b"3\n")
    return path
