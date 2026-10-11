import Base

# Hash assumptions are hypotheses (here: h is collision-free on {x, y}), never axioms.
law cf_push:
  for -h: U32 -> U32
  for x: U32
  for y: U32
  for cf: {h(x) == h(y) : U32} -> {x == y : U32}
  for e: {h(x) == h(y) : U32}
  {x == y : U32}

def cf_push(h, x, y, cf, e):
  cf(e)
