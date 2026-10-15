"""Fixed boards are test fixtures only; production boards are seed-generated."""
import copy
import unittest
from main import (Environment, KnowledgeBase, State, get_successors, heuristic,
                  run_agent, search)


def fixture(rows, start=(0, 0), hidden='T'):
    return Environment([list(row) for row in rows], start, 0, hidden, {})


def knowledge(world):
    kb = KnowledgeBase()
    kb.update_knowledge(world.percept())
    kb.infer()
    return kb


class Lab2Tests(unittest.TestCase):
    def test_bfs_key_then_exit(self):
        w = fixture(['.KE'])
        kb = knowledge(w)
        first = search(w.state, kb, (0, 1), 'BFS')
        self.assertTrue(first.found)
        self.assertTrue(first.states[-1].has_key)
        second = search(first.states[-1], kb, (0, 2), 'BFS')
        self.assertTrue(second.found)
        self.assertEqual(len(first.actions) + len(second.actions), 2)

    def test_astar_avoids_short_trap(self):
        w = fixture(['.TKE', '....'])
        kb = knowledge(w)
        bfs = search(w.state, kb, (0, 2), 'BFS')
        astar = search(w.state, kb, (0, 2), 'A*')
        self.assertEqual((len(bfs.actions), bfs.cost), (2, 9))
        self.assertEqual((len(astar.actions), astar.cost), (4, 4))

    def test_goal_switch_and_retraction(self):
        w = fixture(['.KE'])
        kb = knowledge(w)
        self.assertEqual(kb.choose_goal(), ('Key', (0, 1)))
        w.execute_action('RIGHT')
        kb.update_knowledge(w.percept())
        kb.infer()
        self.assertEqual(kb.choose_goal(), ('Exit', (0, 2)))
        self.assertNotIn(('Goal', 'Key'), kb.facts)
        self.assertNotIn(('HasKey', False), kb.facts)

    def test_unknown_revealed_then_chained(self):
        w = fixture(['.?KE'])
        kb = knowledge(w)
        self.assertIn(('Unknown', (0, 1)), kb.facts)
        self.assertNotIn(('Avoid', (0, 1)), kb.facts)
        self.assertEqual(w.execute_action('RIGHT'), 8)
        kb.update_knowledge(w.percept())
        kb.infer()
        self.assertNotIn(('Unknown', (0, 1)), kb.facts)
        for fact in ('Trap', 'Dangerous', 'Avoid'):
            self.assertIn((fact, (0, 1)), kb.facts)
        self.assertEqual(kb.cost((0, 1)), 8)

    def test_unknown_not_leaked_to_planner(self):
        a = fixture(['.?KE'], hidden='T')
        b = fixture(['.?KE'], hidden='C')
        self.assertEqual(a.percept(), b.percept())
        x = search(a.state, knowledge(a), (0, 2), 'A*')
        y = search(b.state, knowledge(b), (0, 2), 'A*')
        self.assertEqual((x.actions, x.cost), (y.actions, y.cost))
        self.assertEqual(x.cost, 2)

    def test_unreachable_search_failure(self):
        w = fixture(['.WKE'])
        for algorithm in ('BFS', 'A*'):
            result = search(w.state, knowledge(w), (0, 2), algorithm)
            self.assertFalse(result.found)
            metrics, _, _ = run_agent(copy.deepcopy(w), algorithm)
            self.assertEqual(metrics['status'], 'SEARCH_FAILURE')

    def test_bounds_walls_and_locked_exit(self):
        w = fixture(['.EK', 'WWW'])
        self.assertEqual(list(get_successors(w.state, knowledge(w))), [])
        for action in ('UP', 'LEFT', 'DOWN', 'RIGHT'):
            with self.assertRaises(ValueError):
                w.execute_action(action)

    def test_coin_only_once_and_state_fields(self):
        w = fixture(['.CKE'])
        w.execute_action('RIGHT')
        self.assertEqual(w.state.score, 109)
        self.assertEqual(w.state.collected_coins, {(0, 1)})
        w.execute_action('LEFT')
        w.execute_action('RIGHT')
        self.assertEqual(w.state.score, 107)
        self.assertEqual(len(w.state.visited_cells), 2)

    def test_bonus_and_trap_scoring(self):
        w = fixture(['.BTKE'])
        w.bonuses[(0, 1)] = 20
        w.execute_action('RIGHT')
        self.assertEqual(w.state.score, 119)
        w.execute_action('RIGHT')
        self.assertEqual(w.state.score, 103)

    def test_seed_reproducibility_and_comparison(self):
        for seed in (0, 129, -7, 2026):
            w = Environment.generate_world(6, 6, seed)
            same = Environment.generate_world(6, 6, seed)
            self.assertEqual(w.board_text(), same.board_text())
            self.assertEqual(w.hidden, same.hidden)
            original = copy.deepcopy(w)
            for algorithm in ('BFS', 'A*'):
                m, log, agent = run_agent(copy.deepcopy(w), algorithm)
                self.assertTrue(m['goal_reached'])
                self.assertEqual(m['total_path_cost'], m['path_length'] + 7*m['traps'])
                self.assertIn('INFERENCE', log)
                self.assertIn(('Goal', 'Exit'), agent.kb.facts)
            self.assertEqual(w.percept(), original.percept())
        other = Environment.generate_world(6, 6, 130)
        self.assertNotEqual(other.board_text(), Environment.generate_world(6, 6, 129).board_text())

    def test_manhattan_consistency(self):
        w = fixture(['.TKE', '....'])
        kb = knowledge(w)
        goal = (0, 2)
        for p, symbol in kb.visible.items():
            if symbol in 'WE':
                continue
            for _, nxt, cost in get_successors(State(p), kb):
                self.assertLessEqual(heuristic(p, goal), cost + heuristic(nxt.position, goal))

    def test_minimum_board_and_bad_size(self):
        w = Environment.generate_world(3, 3, 129)
        self.assertTrue(run_agent(w, 'A*')[0]['goal_reached'])
        with self.assertRaises(ValueError):
            Environment.generate_world(2, 3, 129)


if __name__ == '__main__':
    unittest.main(verbosity=2)
