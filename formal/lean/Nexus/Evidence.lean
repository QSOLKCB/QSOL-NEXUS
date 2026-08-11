import Nexus.Consensus

namespace Nexus

inductive EvidenceState where
  | untested
  | supported
  | falsified
  deriving Repr, DecidableEq

inductive CouncilOutcome where
  | noConsensus
  | consensus
  deriving Repr, DecidableEq

/-- Council outcome is deliberately not an evidence-state transition. -/
def applyCouncilOutcomeToEvidence
    (evidence : EvidenceState) (_outcome : CouncilOutcome) : EvidenceState :=
  evidence

theorem consensus_does_not_promote_evidence
    (evidence : EvidenceState) (outcome : CouncilOutcome) :
    applyCouncilOutcomeToEvidence evidence outcome = evidence := rfl

end Nexus
