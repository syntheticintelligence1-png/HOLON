# I97's minimized repro of the kernel_fuel construct: bend2 prints ALL PROOFS CHECK, and BendTT (--verdict) prints the
# mismatch text, because its kernel binary stops with "In sub_big: out of fuel". A smaller instance, such as
# Nat.sub(65536n, 1n), checks in both kernels.
import Base
import LAWS.bend as Laws

def Laws.sub_big():
  {==}
