import Nexus.Identity

namespace Nexus

abbrev Roster := List Participant

def seatCount (roster : Roster) : Nat := roster.length

def seatWeights (roster : Roster) : List Nat := roster.map voteWeight

theorem every_seat_weight_one (roster : Roster) :
    seatWeights roster = List.replicate roster.length 1 := by
  induction roster with
  | nil => rfl
  | cons participant rest ih =>
      change 1 :: seatWeights rest = 1 :: List.replicate rest.length 1
      exact congrArg (fun weights => 1 :: weights) ih

/-- Same-seat relief is modeled as replacement, not insertion. -/
def reliefRoster (roster : Roster) (replacement : Participant → Participant) : Roster :=
  roster.map replacement

theorem relief_replacement_does_not_create_extra_seat
    (roster : Roster) (replacement : Participant → Participant) :
    seatCount (reliefRoster roster replacement) = seatCount roster := by
  simp [seatCount, reliefRoster]

end Nexus
