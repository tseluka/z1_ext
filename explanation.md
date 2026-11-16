# Z1 arm on a 7th-axis rail: how this project works

This repo runs the Unitree Z1 arm in Gazebo, mounted on a linear rail (the "7th axis").
The rail is built from the CAD in `cad/whole12.zip`. The arm is driven by Unitree's own
controller, and the rail has its own controller driven from the same keyboard.

Step-by-step setup and troubleshooting: [`todo_sim.md`](todo_sim.md).

---

## 1. What's in the repo

| Path | Origin | Role |
|---|---|---|
| `z1_controller/` | Unitree (vendored, with build fixes) | Arm controller. `main.cpp` builds `z1_ctrl` (real arm); `sim/` builds `sim_ctrl` (Gazebo). The logic is in the closed-source `lib/libZ1_x86_64.so`; `include/` has only its headers. |
| `z1_controller/sim/RailTeleop.*` | added | Keyboard and calibration control of the rail inside `sim_ctrl`. |
| `z1_sdk/` | Unitree | Client library and examples that command the controller over UDP. |
| `z1_ext_gazebo/` | added | ROS package: the Z1 on the rail in Gazebo (model, controller config, launch file). |
| `cad/` | added | Rail CAD, part placements, generator and check scripts, FreeCAD model. |
| `todo_sim.md` | added | Setup and run steps. |

Unitree's Gazebo packages (`unitree_ros`: `z1_description`, `unitree_legged_control`, …)
aren't in this repo. They're cloned into `~/catkin_ws/src` inside the container, and
`z1_ext_gazebo` is symlinked next to them.

## 2. Where things run

```
Host (Arch/Omarchy)                       Docker container "z1sim" (Ubuntu 20.04, ROS Noetic, Gazebo 11)
───────────────────                       ─────────────────────────────────────────────────────────────
~/Desktop/projects/z1_ext  ── mounted ──▶ /z1_ext          (edit on host, build/run in container)
X11 / XWayland display     ◀── xhost ──── Gazebo window
                                          ~/catkin_ws       (unitree_ros + symlink to /z1_ext/z1_ext_gazebo)
```

Unitree's sim needs ROS 1 Noetic, which only supports Ubuntu 20.04, hence the container.
`--net=host` puts the controller's UDP ports and ROS on the host's network.

## 3. Runtime: who talks to whom

```
 ┌──────────────┐  UDP 127.0.0.1:8071/8072   ┌──────────────────────────── sim_ctrl ───────────────────────────────┐
 │ z1_sdk app   │ ─────────────────────────▶ │ cmdPanel (Keyboard or ARMSDK)                                         │
 └──────────────┘        (SDK mode)          │     │ state keys / values                                           │
 ┌──────────────┐                            │     ▼                                                               │
 │ keyboard     │ ─────────────────────────▶ │ FSM (libZ1, 250 Hz): Passive, JointCtrl, Cartesian, Calibration…    │
 └──────────────┘        (k mode)            │     │ LowlevelCmd (q, dq, tau, kp, kd) ×7                            │
                                             │     ▼                                                               │
                                             │ IOROS ── MotorCmd ──▶ /z1_gazebo/JointXX_controller/command  (×6+gripper)
                                             │       ◀─ MotorState ── /z1_gazebo/JointXX_controller/state          │
                                             │                                                                     │
                                             │ RailTeleop (100 Hz) ── Float64 ──▶ /z1_gazebo/rail_controller/command│
                                             │                    ◀─ JointState ─ /z1_gazebo/joint_states (once)   │
                                             └─────────────────────────────────────────────────────────────────────┘
                                                                     │ ROS topics
                                                                     ▼
 ┌────────────────────────────────────── Gazebo (z1_rail.launch) ────────────────────────────────────────────────┐
 │ gazebo_ros_control, namespace /z1_gazebo:                                                                        │
 │   Joint01..06_controller, gripper_controller : unitree_legged_control/UnitreeJointController (emulates Z1 motors)│
 │   rail_controller        : effort_controllers/JointPositionController on rail_joint (PID → force)               │
 │   joint_state_controller : publishes /z1_gazebo/joint_states (1000 Hz)                                         │
 │ Physics: ODE, 0.2 ms step                                                                                       │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Arm path (Unitree's design, unchanged)
1. **Input:** keys (or SDK packets) become *state requests* (e.g. `2` = joint control) and
   *values* (e.g. `q`/`a` held = joint 1 ±).
2. **Control:** the FSM in `libZ1` runs the active state at 250 Hz and computes a low-level
   command per joint: target position and velocity, feed-forward torque, and gains.
3. **To Gazebo:** `sim/IOROS.cpp` turns each command into a `MotorCmd` message, converting
   gains into the plugin's units (`Kp×25.6`, `Kd×0.0128`). It publishes them and reads back
   each joint's `MotorState`.
4. **Simulation:** in Gazebo, `UnitreeJointController` turns each `MotorCmd` into joint torque,
   like the real Z1 motors do.

On the real arm the same FSM runs in `z1_ctrl`, and only the I/O layer differs (UDP to the
arm). That's why SDK code runs unchanged on sim and hardware.

### Rail path (added)
1. **Keys:** `sim_ctrl k` registers one more key pair, `x`/`z`, as the 8th `ValueAction`.
   While a key is held, `cmdPanel->getDirections()[7]` reads +1 or −1.
2. **Startup:** `RailTeleop` waits for one `/z1_gazebo/joint_states` message and takes
   `rail_joint`'s current position as its starting target, so the carriage never jumps.
   No `rail_joint` (plain `z1.launch`) means it prints `rail jog off` and does nothing.
3. **Jogging:** every 10 ms the target moves by direction × `rail_speed` × dt, is clamped to
   ±0.52 m, and is published to `rail_controller`.
4. **Following:** `rail_controller` is a PID (p 2000, d 250, up to 200 N) that pushes the
   carriage toward the target.
5. **Calibration:** `sim_ctrl` replaces Unitree's calibration state with
   `State_CalibrationRail`. When the FSM really enters calibration, its `enter()` sets a
   thread-safe flag. `RailTeleop` then ramps the target to `rail_calib_pos` (default
   −0.52 m, the left end). Holding `x`/`z` cancels the move.

The arm FSM doesn't know about the 7th axis. Arm kinematics and the SDK treat the arm as
fixed on its base, and the base just happens to move.

## 4. The simulated robot model

`z1_rail.launch` builds the model from `z1_ext_gazebo/urdf/z1_on_rail.xacro` and spawns it
as `z1_gazebo`. The name must match, because every topic lives under `/z1_gazebo/`.

```
world
 └─ rail_static_joint (fixed, z +30 mm: board underside on the ground)
     └─ rail_base      board, rail strips, dovetail rails, hard stops, rack, cable trough, chain block
         └─ rail_joint (prismatic along x, ±0.52 m, effort-driven)
             └─ carriage    runners, carriage plate, steel plate, pinion, chain block
                 └─ base_static_joint (fixed, z +68 mm = top of steel plate)
                     └─ link00 → joint1 … joint6 → gripper     (Unitree's Z1, unchanged)
```

| File | Role |
|---|---|
| `urdf/z1_on_rail.xacro` | Unitree's `robot.xacro` (commit `fa9b011d`) with **only the base joint changed** (now hangs off `carriage`), plus the rail joint and its transmission. |
| `urdf/rail.xacro` | **Generated** by `cad/tools/gen_rail_xacro.py`, never hand-edited: every rail part as a mesh at its CAD position, with mass and inertia from the meshes. |
| `meshes/*.stl` | The 14 part meshes used (unchanged copies from the zip, mm, scaled 0.001). |
| `config/rail_control.yaml` | `rail_controller` settings. |
| `launch/z1_rail.launch` | Replaces `unitree_gazebo/z1.launch`: same arm controllers, plus the rail. |
| `worlds/z1_rail.world` | Unitree's physics settings, ground, sun. |

**Collision:** most parts can collide. The runners (about 0.3 mm clearance on the
dovetail), the pinion (meshes with the rack) and the carriage-side chain block are visual
only, so they can't jam the slide. The prismatic joint does the guiding.

**Assumptions:** the CAD doesn't record materials, so masses use aluminium, steel, MDF and
plastic (base ≈ 39 kg, carriage ≈ 6.4 kg). The controller gains, 200 N limit and 0.5 m/s
are starting values. The pinion doesn't spin, and the motor isn't modelled.

### Launch sequence
1. roscore + Gazebo with `worlds/z1_rail.world` (paused).
2. xacro → parameter `robot_description`.
3. `spawn_model` creates `z1_gazebo` and unpauses.
4. Loads Unitree's `robot_control.yaml` + `config/rail_control.yaml`.
5. Starts `joint_state_controller`, `Joint01…06_controller`, `gripper_controller`,
   `rail_controller`.
6. `robot_state_publisher` turns joint states into coordinate frames (TF).

## 5. From CAD to model (`cad/`)

| Path | Role |
|---|---|
| `whole12.zip`, `whole12/` | The CAD: 15 part STLs, each in its own frame (mm), plus `00_full_assembly.stl`. |
| `whole12_placements.json` | Where each of the 34 part copies sits in the assembly (all pure translations). |
| `tools/place_parts.py` | Finds the placements by matching each part's vertices against the assembly (24 axis rotations, 0.05 mm tolerance). |
| `tools/verify_placements.py` | Confirms the placed parts rebuild the assembly **triangle for triangle** (41004, none missing, none extra). |
| `tools/gen_rail_xacro.py` | Splits parts into fixed and moving, computes mass properties, writes `z1_ext_gazebo/urdf/rail.xacro`. |
| `tools/freecad_import_rail.py` | FreeCAD macro that builds the rail as separate placed parts (see §7). |
| `whole12_rail.FCStd` | The FreeCAD model that macro produces. |

**Travel limit:** a mesh clash check over the full stroke found the runners hit the hard
stops at exactly ±520 mm, hence ±0.52 m.

**Problems found in the CAD (worth fixing at the source):**
- The carriage-side drag-chain block cuts into one rail by about 1140 mm³, at every position.
- The lower pinion disc and one pin cut into one rail strip by about 734 mm³.
- `15_brake_block.stl` isn't used in the assembly, so it isn't in the model.

**If the CAD changes:** update `cad/whole12/`, then run `place_parts.py` →
`verify_placements.py` → `gen_rail_xacro.py` (needs `numpy` + `trimesh`), then `catkin_make`.

## 6. How to run

Full detail is in `todo_sim.md`. In short: steps 1–2 are on the host, everything else is in the container.

**One time**
```bash
# host: Docker + display access, then reboot
sudo pacman -S --needed docker xorg-xhost
sudo systemctl enable --now docker && sudo usermod -aG docker $USER

# host: create the container
xhost +SI:localuser:root
docker run -it --name z1sim --net=host --ipc=host \
  -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 -v /tmp/.X11-unix:/tmp/.X11-unix \
  --device /dev/dri -v ~/Desktop/projects/z1_ext:/z1_ext osrf/ros:noetic-desktop-full bash

# container: ROS packages + workspace
apt update && apt install -y git ros-noetic-ros-control ros-noetic-ros-controllers \
  ros-noetic-gazebo-ros-control ros-noetic-joint-state-controller \
  ros-noetic-effort-controllers libeigen3-dev libboost-dev
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src
git clone https://github.com/unitreerobotics/unitree_ros.git
git clone https://github.com/unitreerobotics/unitree_ros_to_real.git
mv unitree_ros_to_real/unitree_legged_msgs . && rm -rf unitree_ros_to_real
ln -s /z1_ext/z1_ext_gazebo ~/catkin_ws/src/
cd ~/catkin_ws && source /opt/ros/noetic/setup.bash && catkin_make
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc && source ~/.bashrc

# container: build sim_ctrl (again whenever z1_controller/sim changes)
cd /z1_ext/z1_controller && mkdir -p build_sim && cd build_sim && cmake .. && make -j$(nproc)
```

**Every session**
```bash
# host
xhost +SI:localuser:root && docker start -ai z1sim
# terminal 1 (container): wait for "Started controllers: … rail_controller", press Play
roslaunch z1_ext_gazebo z1_rail.launch
# terminal 2 (host: docker exec -it z1sim bash): wait for "[rail] keyboard jog on"
cd /z1_ext/z1_controller/build_sim && ./sim_ctrl k
```

**Keys in `sim_ctrl k`**

| Key | Action |
|---|---|
| `` ` `` | Arm back to start pose |
| `1` | Passive |
| `2` | Joint control: q/a, w/s, e/d, r/f, t/g, y/h move joints 1–6 |
| `3` | Cartesian control |
| `=` | Calibration; also drives the carriage to the left end (−0.52 m) |
| `x` / `z` (hold) | Move the carriage +x / −x at 0.1 m/s, limited to ±0.52 m |

**Rail settings** (set before starting `sim_ctrl`): `rosparam set /z1_controller/rail_speed 0.2`,
also `rail_lower`, `rail_upper`, `rail_calib_pos` (metres).
**Direct command:** `rostopic pub -1 /z1_gazebo/rail_controller/command std_msgs/Float64 "data: 0.3"`.
SDK mode (`./sim_ctrl` without `k`) drives the arm only.

## 7. Viewing the rail in FreeCAD

- **Open:** `cad/whole12_rail.FCStd`.
- **Rebuild instead:** Macro → Macros… → set the macro location to `cad/tools/` → run
  `freecad_import_rail.py`. From a terminal, `freecadcmd cad/tools/freecad_import_rail.py`
  regenerates the `.FCStd`.
- **Groups:** `RailBase` (15 fixed parts) and `Carriage` (19 moving parts), in mm, in the
  same frame as `00_full_assembly.stl`.
- **Sliding:** change Carriage → Placement → Position → x (−520 … 520).
- **Solids:** parts are meshes. Set `MAKE_SOLIDS = True` in the macro for Part solids
  (needed for STEP export, cutting, picking faces and edges).

## 8. Limits
- The rail is invisible to the arm controller: no coordinated 7-axis motion, and the SDK
  can't command the rail.
- Simplified drive: the pinion doesn't spin and the motor isn't modelled.
- Masses are based on assumed materials, and the controller gains are starting values.
- So far the Gazebo model and the rail code have been checked on the host only (URDF
  parsing, compiling against stand-in ROS headers, keyboard behaviour with the real
  `libZ1`). They haven't yet been built against real ROS or run in Gazebo.
