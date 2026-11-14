# z1_ext

Unitree Z1 arm workspace: vendored copies of the official controller and SDK, set up to build on a current Arch Linux system.

| Directory | Upstream | Commit |
|---|---|---|
| `z1_controller/` | https://github.com/unitreerobotics/z1_controller | `639bb773bd11b0e8495faf40eadc9e8eb8bc8400` |
| `z1_sdk/` | https://github.com/unitreerobotics/z1_sdk | `f1af2b42f2a39a5010946e049ad3fe324e2e6f06` |

Local changes vs upstream:
- `z1_sdk/CMakeLists.txt`: link `Eigen3::Eigen` to the Python module (pybind11 includes `<Eigen/Core>`).

## Architecture

```
your program --(z1_sdk API, UDP 127.0.0.1:8071/8072)--> z1_ctrl --(UDP 192.168.123.110:8881)--> Z1 arm
```

- `z1_ctrl` (z1_controller) always runs. It is a 250 Hz finite state machine that talks to the arm.
- `z1_sdk` is the C++/Python client library for controlling the arm from code via `z1_ctrl`.

## Dependencies (Arch)

```
sudo pacman -S --needed base-devel cmake eigen boost pybind11
```

## Build

CMake 4.x needs `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` because both projects declare an old minimum version.

```
cmake -S z1_controller -B z1_controller/build -DCMAKE_POLICY_VERSION_MINIMUM=3.5 && cmake --build z1_controller/build
cmake -S z1_sdk        -B z1_sdk/build        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 && cmake --build z1_sdk/build
```

The SDK build also produces a Python module for your interpreter version in `z1_sdk/lib/`.

## Network

The arm's IP is `192.168.123.110`. Put the PC on the same subnet:

```
sudo ip addr add 192.168.123.162/24 dev <eth-interface>
ping 192.168.123.110
```

## Run

`z1_ctrl` must be started from its `build/` directory because it reads `../config/config.xml`.

**Keyboard mode:** `cd z1_controller/build && ./z1_ctrl k`

| Key | Action |
|---|---|
| `` ` `` | back to start |
| `1` | passive |
| `2` | joint control: q/a w/s e/d r/f t/g y/h move joints 1–6; up/down move the gripper |
| `3` | Cartesian control |
| `4` `5` `6` | MoveJ / MoveL / MoveC |
| `7` `8` | teach / teach-repeat |
| `9` `0` | save state / to state |
| `-` | trajectory |
| `=` | calibration |

**SDK mode:**

```
cd z1_controller/build && ./z1_ctrl                    # terminal 1
cd z1_sdk/build && ./highcmd_basic                     # terminal 2 (C++)
cd z1_sdk/examples_py && python3 example_highcmd.py    # or Python
```

The controller tries to get real-time scheduling (SCHED_FIFO). That only works as root, so run it with `sudo` if motion jitters.

## Safety

- Examples move the arm immediately. Keep the e-stop within reach.
- Collision detection is off by default (`z1_controller/config/config.xml` → `<collision><open>N`).

Docs: https://support.unitree.com/home/en/Z1_developer
