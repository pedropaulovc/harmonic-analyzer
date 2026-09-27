from explore2 import *
T=-81.87561109753875
def show(r): print({k: (round(v,4) if isinstance(v,float) else v) for k,v in r.items()})
print('A/B: K5.3 drop-7 pin20')
for h in (9.0, 9.1, 9.2, 9.25, 9.3, 9.4, 9.5):
    show(solve_E(h, -7.0, 5.3, T, 20.0))
print('A alt drop -6')
for h in (9.0, 9.25):
    show(solve_E(h, -6.0, 5.3, T, 20.0))
print('C: K4.8 (wall 1.615) drop-6 pin 17/20')
for h in (8.0, 8.25, 8.5, 8.75, 9.0):
    show(solve_E(h, -6.0, 4.8, T, 17.0))
