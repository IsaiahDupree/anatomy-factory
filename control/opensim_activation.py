#!/usr/bin/env python3
"""opensim_activation.py — OpenSim -> per-muscle activation time-series -> JSON.

Two modes:
  (a) demo   : build a 1-muscle model, drive a ramp excitation, export activation(t).
  (b) model  : load an .osim + a .sto controls/excitation file, forward-simulate,
               export {muscle_name -> [activation over time]} sampled at fps.

The exported JSON (normalized 0..1 per muscle) is exactly what render_scene.py's
"activation" pass keys per muscle name to drive emission/heatmap color.

Usage:
  python opensim_activation.py demo <out.json> [dur_s] [fps]
  python opensim_activation.py model <model.osim> <controls.sto> <out.json> [dur_s] [fps]
Run in the opensim venv:  C:\\AnatomyFactory\\venvs\\opensim\\Scripts\\python.exe
"""
import sys, json
import opensim as osim

def build_demo_model():
    m = osim.Model(); m.setName("one_muscle_demo")
    body = osim.Body("b", 1.0, osim.Vec3(0), osim.Inertia(0.1, 0.1, 0.1, 0, 0, 0)); m.addBody(body)
    j = osim.PinJoint("j", m.getGround(), osim.Vec3(0), osim.Vec3(0), body, osim.Vec3(0, 0.5, 0), osim.Vec3(0)); m.addJoint(j)
    mus = osim.Thelen2003Muscle("biceps", 200.0, 0.1, 0.1, 0.0)
    mus.addNewPathPoint("o", m.getGround(), osim.Vec3(0.1, 0, 0))
    mus.addNewPathPoint("i", body, osim.Vec3(0, 0, 0))
    m.addForce(mus)
    ctrl = osim.PrescribedController(); ctrl.addActuator(mus)
    # ramp excitation 0 -> 1 over 1s then hold
    fn = osim.PiecewiseLinearFunction()
    fn.addPoint(0.0, 0.02); fn.addPoint(1.0, 1.0); fn.addPoint(10.0, 1.0)
    ctrl.prescribeControlForActuator("biceps", fn)
    m.addController(ctrl)
    return m

def muscle_names(m):
    ms = m.getMuscles(); return [ms.get(i).getName() for i in range(ms.getSize())]

def simulate(m, dur, fps):
    s = m.initSystem(); s.setTime(0.0)
    mgr = osim.Manager(m); mgr.initialize(s)
    names = muscle_names(m)
    ms = m.getMuscles()
    times, series = [], {n: [] for n in names}
    n = max(1, int(round(dur * fps)))
    for i in range(1, n + 1):
        t = i / fps
        s = mgr.integrate(t)
        m.realizeDynamics(s)
        times.append(round(t, 4))
        for k in range(ms.getSize()):
            mu = ms.get(k)
            series[mu.getName()].append(round(mu.getActivation(s), 4))
    return times, series

def main():
    mode = sys.argv[1]
    if mode == "demo":
        outp = sys.argv[2]; dur = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
        fps = int(sys.argv[4]) if len(sys.argv) > 4 else 24
        m = build_demo_model()
    else:
        model, controls, outp = sys.argv[2], sys.argv[3], sys.argv[4]
        dur = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
        fps = int(sys.argv[6]) if len(sys.argv) > 6 else 24
        m = osim.Model(model)
        ctrl = osim.PrescribedController(controls); m.addController(ctrl)
    times, series = simulate(m, dur, fps)
    import os
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    json.dump({"fps": fps, "dur_s": dur, "opensim": osim.__version__,
               "times": times, "muscles": series}, open(outp, "w"), indent=1)
    print("OPENSIM_ACTIVATION_OK muscles=", list(series.keys()), "samples=", len(times), "->", outp)
    for k, v in series.items():
        print(f"  {k}: start={v[0]} peak={max(v)} end={v[-1]}")

if __name__ == "__main__":
    main()
