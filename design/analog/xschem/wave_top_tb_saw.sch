v {xschem version=3.4.0 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {r2r_dac8_pdk.sym} 600 0 0 0 {name=XDAC}
C {stair_stepper_saw.sym} 100 0 0 0 {name=XSTEP}
N 400 30 600 30 {lab=b7}
N 400 90 600 90 {lab=b6}
N 400 150 600 150 {lab=b5}
N 400 210 600 210 {lab=b4}
N 400 270 600 270 {lab=b3}
N 400 330 600 330 {lab=b2}
N 400 390 600 390 {lab=b1}
N 400 450 600 450 {lab=b0}
C {devices/vsource.sym} 1030 510 0 0 {name=EVREF value=1.8}
N 900 480 1030 480 {lab=vref}
N 1030 540 1030 900 {}
C {devices/vsource.sym} 1000 570 0 0 {name=EVDD value=1.8}
N 900 540 1000 540 {lab=vpwr}
N 1000 600 1000 900 {}
N 900 600 1100 600 {lab=vgnd}
N 1100 600 1100 900 {}
N 1000 900 1100 900 {}
C {devices/gnd.sym} 1050 900 0 0 {name=g1 lab=0}
N 900 660 1000 660 {lab=vfilt}
N 900 720 1000 720 {lab=vout}
C {devices/code.sym} 100 -320 0 0 {name=s_lib value=".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt"}
C {devices/code.sym} 100 -260 0 0 {name=s_tran value=".tran 100p 5.12e-06")}
C {devices/code.sym} 100 -200 0 0 {name=s_save value=".save v(vout) v(vfilt) v(b7) v(b0)"}
C {devices/code.sym} 100 -140 0 0 {name=s_note value="* tb: 256clk staircase replay of the RTL golden (see gen_tb_sch.py)"}
