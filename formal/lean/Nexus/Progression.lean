import Nexus.Citizenship

namespace Nexus

structure AuthorityEffect where
  voteWeightCreated : Nat
  councilSeatsCreated : Nat
  citizenshipChanged : Bool
  evidencePromoted : Bool
  toolAuthorityCreated : Bool
  deriving Repr, DecidableEq

def noAuthority : AuthorityEffect :=
  {
    voteWeightCreated := 0
    councilSeatsCreated := 0
    citizenshipChanged := false
    evidencePromoted := false
    toolAuthorityCreated := false
  }

/-- Descriptive progression history has no governance side effect. -/
def progressionAuthorityEffect (_activityCount : Nat) : AuthorityEffect :=
  noAuthority

theorem progression_creates_no_authority (activityCount : Nat) :
    progressionAuthorityEffect activityCount = noAuthority := rfl

end Nexus
