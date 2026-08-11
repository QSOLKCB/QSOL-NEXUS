import Nexus.Council

namespace Nexus

inductive Ballot where
  | accept
  | acceptWithChanges
  | testFurther
  | reject
  deriving Repr, DecidableEq

/-- Exact two-thirds rule using integer arithmetic: 3*yes >= 2*total. -/
def twoThirdsMet (yes total : Nat) : Bool :=
  decide (2 * total ≤ 3 * yes)

theorem two_thirds_definition_is_exact (yes total : Nat) :
    twoThirdsMet yes total = decide (2 * total ≤ 3 * yes) := rfl

theorem two_of_three_meets_two_thirds : twoThirdsMet 2 3 = true := by
  decide

theorem one_of_three_does_not_meet_two_thirds : twoThirdsMet 1 3 = false := by
  decide

end Nexus
