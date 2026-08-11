import Nexus.Basic

namespace Nexus

/-- A civic seat contains exactly one participant identity. -/
structure CivicSeat where
  participant : Participant
  deriving Repr, DecidableEq

/-- Replacing the model occupying a seat does not alter that seat's weight. -/
def replaceSeatModel (seat : CivicSeat) (replacement : Participant) : CivicSeat :=
  { seat with participant := replacement }

theorem replacing_model_preserves_seat_weight (seat : CivicSeat) (replacement : Participant) :
    voteWeight (replaceSeatModel seat replacement).participant =
      voteWeight seat.participant := rfl

end Nexus
