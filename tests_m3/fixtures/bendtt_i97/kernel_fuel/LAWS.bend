# I97's minimized repro of the kernel_fuel construct (F-M3-13): a claim that bend2 decides by evaluation and the
# BendTT kernel cannot evaluate within its pinned fuel. Nat literals reach the kernel as unary terms, and Nat.sub
# recurses on its second argument, so 131072 - 126976 costs the kernel more than bendtt.lean's FUEL.
import Base

law sub_big:
  {Nat.sub(131072n, 126976n) == 4096n : Nat}
