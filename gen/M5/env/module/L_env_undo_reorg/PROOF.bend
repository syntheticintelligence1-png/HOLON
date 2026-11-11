import Base
import ./LAWS.bend as Laws
import ../../model/env.bend as M

def bot(h: {False{} == True{} : Bool}) -> Empty:
  %h : M.is_false(_)
  Unit{}

def ex_falso(-P: Type, e: Empty) -> P:
  match e:

def bot_eq(-b: Bool, h: {False{} == True{} : Bool}) -> {b == False{} : Bool}:
  ex_falso({b == False{} : Bool}, bot(h))

def Laws.l_env_undo_reorg(k, e, h):
  match k:
    case 0n:
      {==}
    case 1n+k1:
      match k1:
        case 0n:
          {==}
        case 1n+k2:
          match k2:
            case 0n:
              {==}
            case 1n+k3:
              match k3:
                case 0n:
                  {==}
                case 1n+k4:
                  match k4:
                    case 0n:
                      {==}
                    case 1n+k5:
                      match k5:
                        case 0n:
                          {==}
                        case 1n+k6:
                          match k6:
                            case 0n:
                              {==}
                            case 1n+k7:
                              match k7:
                                case 0n:
                                  {==}
                                case 1n+k8:
                                  match k8:
                                    case 0n:
                                      {==}
                                    case 1n+k9:
                                      match k9:
                                        case 0n:
                                          {==}
                                        case 1n+k10:
                                          match k10:
                                            case 0n:
                                              {==}
                                            case 1n+k11:
                                              bot_eq(M.lt(1n+k11, e), h)
