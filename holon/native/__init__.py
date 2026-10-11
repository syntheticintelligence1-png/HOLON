"""holon.native — M2 S7: the compiled generated model as a callable library.

bendc compiles each gen model to C and links it with shim.c into libmodel.so;
the holonmodel Go binary (cgo) and the forge harnesses feed both sides the
same inputs; refine.py writes replay/M2/refinement/<edge>.json.
"""
