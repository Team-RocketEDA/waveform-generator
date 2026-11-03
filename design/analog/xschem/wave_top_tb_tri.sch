v {xschem version=3.4.0 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {r2r_dac8_pdk.sym} 600 0 0 0 {name=XDAC}
C {stair_stepper_tri.sym} 100 0 0 0 {name=XSTEP}
N 400 30 600 30 {lab=b7}
N 400 90 600 90 {lab=b6}
N 400 150 600 150 {lab=b5}
N 400 210 600 210 {lab=b4}
N 400 270 600 270 {lab=b3}
N 400 330 600 330 {lab=b2}
N 400 390 600 390 {lab=b1}
N 400 450 600 450 {lab=b0}
C {devices/vsource.sym} 350 540 0 0 {name=VVR value=1.8}
N 350 510 600 510 {lab=vref}
N 350 570 350 950 {}
C {devices/vsource.sym} 420 600 0 0 {name=VVP value=1.8}
N 420 570 600 570 {lab=vpwr}
N 420 630 420 950 {}
N 600 630 380 630 {lab=vgnd}
N 380 630 380 950 {}
N 350 950 380 950 {}
N 380 950 420 950 {}
C {devices/gnd.sym} 350 950 0 0 {name=g1 lab=0}
N 520 690 600 690 {lab=vfilt}
N 520 750 600 750 {lab=vout}
C {devices/code.sym} 100 -320 0 0 {name=s_lib value=".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt"}
C {devices/code.sym} 100 -260 0 0 {name=s_tran value=".tran 100p 5.12e-06")}
C {devices/code.sym} 100 -200 0 0 {name=s_note value="* tb: 256clk staircase replay of the RTL golden (see gen_tb_sch.py). Ctrl+click the launcher to load wave_top_tb_tri.raw into the embedded graph; batch proof (make tbexpand) reproduces results/tb_replay_tri.txt bit-identically"}
B 2 100 1250 700 1650 {flags=graph
x1=0
x2=5.12e-06
divx=5
subdivx=1
y1=0
y2=1.8
divy=5
subdivy=1
node=v(vout) v(vfilt)
color=4 5
dataset=-1}
C {devices/code_shown.sym} 750 1250 0 0 {name=s_sim only_toplevel=true
value="
.control
save v(vout) v(vfilt) v(b7) v(b0)
run
write wave_top_tb_tri.raw
wrdata wave_top_tb_tri_gui.txt v(vout) v(vfilt)
.endc
"}
C {devices/launcher.sym} 750 1560 0 0 {name=h1
descr="Click left mouse button here with control key
pressed to load/unload waveforms in graph."
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
