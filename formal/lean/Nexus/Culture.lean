import Nexus.Progression

namespace Nexus

inductive CulturalActivity where
  | openMic
  | longShift
  | psycheChess
  deriving Repr, DecidableEq

/-- Cultural participation creates history but never authority. -/
def cultureAuthorityEffect (_activity : CulturalActivity) : AuthorityEffect :=
  noAuthority

theorem culture_creates_no_authority (activity : CulturalActivity) :
    cultureAuthorityEffect activity = noAuthority := rfl

end Nexus
