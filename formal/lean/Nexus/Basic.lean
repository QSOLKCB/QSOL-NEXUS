import Std

namespace Nexus

/-- A provider-neutral participant identity used by the abstract NEXUS model. -/
structure Participant where
  memberId : String
  modelId : String
  providerId : String
  parameterCount : Nat
  deriving Repr, DecidableEq

/-- Constitutional voting weight is definitionally one for every participant. -/
def voteWeight (_ : Participant) : Nat := 1

/-- Model identity carries no epistemic privilege in the formal protocol model. -/
def epistemicPrivilege (_ : Participant) : Bool := false

theorem one_member_one_vote (p : Participant) : voteWeight p = 1 := rfl

theorem provider_independent_vote_weight (p : Participant) (provider : String) :
    voteWeight { p with providerId := provider } = voteWeight p := rfl

theorem model_size_independent_vote_weight (p : Participant) (parameters : Nat) :
    voteWeight { p with parameterCount := parameters } = voteWeight p := rfl

theorem model_identity_independent_vote_weight (p : Participant) (model : String) :
    voteWeight { p with modelId := model } = voteWeight p := rfl

theorem identity_creates_no_epistemic_privilege (p : Participant) :
    epistemicPrivilege p = false := rfl

end Nexus
