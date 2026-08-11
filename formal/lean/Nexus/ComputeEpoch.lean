import Nexus.Basic

namespace Nexus

/-- Protected-small admission ceiling: 20B parameters, expressed in millions, doubling per epoch. -/
def protectedSmallCeiling (epoch : Nat) : Nat :=
  20000 * (2 ^ epoch)

/-- Epoch capability policy does not alter constitutional vote weight. -/
def epochVoteWeight (participant : Participant) (_epoch : Nat) : Nat :=
  voteWeight participant

theorem capability_growth_does_not_change_vote_weight
    (participant : Participant) (epochA epochB : Nat) :
    epochVoteWeight participant epochA = epochVoteWeight participant epochB := rfl

end Nexus
