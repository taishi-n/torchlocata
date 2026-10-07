# Geometry and DOA

## World-to-array coordinates

The [official MATLAB implementation](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/get_truth.m)
defines an array-frame vector from world source position `h`, array origin `p`,
and local-to-world rotation `R` as:

```text
v = R.T @ (h - p)
```

`world_to_array(source_position, array_position, array_rotation)` applies this
formula to tensors explicitly treated as simultaneous. Positions end in shape
`3`; rotations end in `[3, 3]`; leading dimensions must broadcast. The output is
float64. It validates finite geometry, orthonormal rotations, and determinant
`+1`, with `1e-5` absolute and relative tolerances.

Raw dataset poses retain nonfinite geometry. This explicit helper rejects it
rather than generating an artificial direction.

## Angle convention

`locata_doa(array_pose, source_pose)` returns a `DOA` typed dict:

| Field | Shape | Units and convention |
| --- | --- | --- |
| `vector` | `[P, 3]` | Array-frame xyz in metres |
| `azimuth` | `[P]` | Radians in `[-pi, pi)`, with +y at zero |
| `inclination` | `[P]` | Radians in `[0, pi]`, measured from +z |
| `range` | `[P]` | Source-to-array distance in metres |

The [official spherical conversion](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/mycart2sph.m)
uses `atan2(v_y, v_x) - pi/2` for azimuth, with wrapping, and
`acos(v_z / norm(v))` for its angle named elevation. This library calls the latter
`inclination` to distinguish it from elevation above the horizontal plane.

| Array-frame direction | Azimuth | Inclination |
| --- | --- | --- |
| +y | `0` | `pi/2` |
| +x | `-pi/2` | `pi/2` |
| -x | `pi/2` | `pi/2` |
| -y | `-pi` | `pi/2` |
| +z | `-pi/2` | `0` |
| -z | `-pi/2` | `pi` |

The -y boundary is represented as `-pi`; MATLAB's occasional `+pi` denotes the
same direction. On the z axis, azimuth follows `atan2(0, 0)` and is represented
as `-pi/2`. Zero distance raises an error because the direction is undefined.

## Time alignment

Both pose clocks and their calendar origins must match exactly for `locata_doa`.
Pose arrays must also have matching row shapes. A mismatch raises `ValueError`;
the helper does not silently pair annotation rows from different times.

The reader provides no interpolation. Callers must explicitly establish aligned,
valid poses before deriving directions. Elementwise linear interpolation of a
rotation matrix is not a supported operation. See [time and
windows](time-and-windows.md) for the raw clock and cropping contract, and the
[API reference](api.md) for signatures.
