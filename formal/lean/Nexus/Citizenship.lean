import Nexus.Council

namespace Nexus

structure CivicIdentity where
  participant : Participant
  citizen : Bool
  deriving Repr, DecidableEq

def civicVoteWeight (identity : CivicIdentity) : Nat :=
  voteWeight identity.participant

theorem citizenship_does_not_change_vote_weight (participant : Participant) :
    civicVoteWeight { participant := participant, citizen := true } =
      civicVoteWeight { participant := participant, citizen := false } := rfl

/-- A civic proxy is a representation of one seat, never an additional seat. -/
def proxyRoster (roster : Roster) (proxy : Participant → Participant) : Roster :=
  roster.map proxy

theorem civic_proxy_does_not_create_extra_vote
    (roster : Roster) (proxy : Participant → Participant) :
    seatCount (proxyRoster roster proxy) = seatCount roster := by
  simp [proxyRoster, seatCount]

end Nexus
