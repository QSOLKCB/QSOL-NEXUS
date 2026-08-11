import Nexus.Basic

namespace Nexus

inductive Hat where
  | white
  | red
  | black
  | yellow
  | green
  | blue
  deriving Repr, DecidableEq

def nextHat : Hat → Option Hat
  | .white => some .red
  | .red => some .black
  | .black => some .yellow
  | .yellow => some .green
  | .green => some .blue
  | .blue => none

theorem six_hats_sequence_closed :
    nextHat .white = some .red ∧
    nextHat .red = some .black ∧
    nextHat .black = some .yellow ∧
    nextHat .yellow = some .green ∧
    nextHat .green = some .blue ∧
    nextHat .blue = none := by
  decide

structure HatCommit where
  hat : Hat
  payloadHash : String
  sealed : Bool
  deriving Repr, DecidableEq

def sealHat (commit : HatCommit) : HatCommit :=
  { commit with sealed := true }

theorem sealed_phase_payload_immutable (commit : HatCommit) :
    (sealHat commit).payloadHash = commit.payloadHash := rfl

theorem sealed_phase_hat_immutable (commit : HatCommit) :
    (sealHat commit).hat = commit.hat := rfl

end Nexus
