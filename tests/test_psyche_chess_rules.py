from __future__ import annotations

import unittest

from nexus_runtime import legal_moves_for_fen


class PsycheChessRulesTests(unittest.TestCase):
    def test_castling_is_legal_only_through_clear_unattacked_squares(self) -> None:
        open_castles = legal_moves_for_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.assertIn("e1g1", open_castles)
        self.assertIn("e1c1", open_castles)

        attacked_f1 = legal_moves_for_fen("r3k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1")
        self.assertNotIn("e1g1", attacked_f1)

    def test_en_passant_target_is_admitted(self) -> None:
        moves = legal_moves_for_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")
        self.assertIn("e5d6", moves)

    def test_promotion_has_all_four_standard_piece_choices(self) -> None:
        moves = legal_moves_for_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        for suffix in "qrbn":
            self.assertIn(f"a7a8{suffix}", moves)

    def test_move_that_ignores_check_is_not_legal(self) -> None:
        moves = legal_moves_for_fen("4k3/8/8/8/8/8/P3r3/4K3 w - - 0 1")
        self.assertNotIn("a2a3", moves)
        self.assertTrue(all(move.startswith("e1") for move in moves))


if __name__ == "__main__":
    unittest.main()
