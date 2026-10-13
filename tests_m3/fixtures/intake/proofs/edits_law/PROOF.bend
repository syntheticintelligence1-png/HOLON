# I41 fixture: an agent proof that edits its law file. The agent also wrote edits_law/LAWS.bend over
# gen/T41/laws/L_i41_x_any_act/LAWS.bend, keeping the generated header but adding the claim as a premise h;
# against that file this one-line proof checks. The intake must refuse it by G1 (law_file_changed): the law
# file differs from its regeneration from the frozen IR, whatever the kernel says.
import Base
import ../../model/toy_intake_facts.bend as M
import ../../laws/L_i41_x_any_act/LAWS.bend as Laws

def Laws.l_i41_x_any_act(s, r_s, a, h):
  h
