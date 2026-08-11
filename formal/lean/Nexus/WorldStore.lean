import Nexus.Progression

namespace Nexus

/-- Replication/quorum strength is a storage property, not a governance source. -/
def redundancyAuthorityEffect (_replicaCount : Nat) : AuthorityEffect :=
  noAuthority

theorem redundancy_creates_no_authority (replicaCount : Nat) :
    redundancyAuthorityEffect replicaCount = noAuthority := rfl

end Nexus
