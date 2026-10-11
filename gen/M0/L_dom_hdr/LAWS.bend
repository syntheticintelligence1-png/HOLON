import Base
import ../model/morph_header.bend as M

law cl_l_dom_hdr:
  exs b: List<&2, U32>
  {M.ok_sol(b) != M.ok_go(b) : Bool}
