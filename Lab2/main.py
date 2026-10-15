"""Smart Escape II. Python standard library only; see README.md."""
from __future__ import annotations
import argparse
import copy
import csv
import heapq
import json
import random
from collections import deque
from dataclasses import dataclass, replace
from itertools import count
from pathlib import Path
from time import perf_counter

STUDENT_ID = 'B242270129'
DIRECTIONS = {'UP': (-1, 0), 'DOWN': (1, 0), 'LEFT': (0, -1), 'RIGHT': (0, 1)}
NAMES = {'.': 'Empty', 'W': 'Wall', 'T': 'Trap', 'C': 'Coin',
         'B': 'Bonus', 'K': 'Key', 'E': 'Exit', '?': 'Unknown'}


@dataclass(frozen=True)
class State:
    position: tuple[int, int]
    has_key: bool = False
    score: int = 100
    collected_coins: frozenset = frozenset()
    visited_cells: frozenset = frozenset()
    consumed: frozenset = frozenset()


def transition(state, position, symbol, bonus=5):
    """Successor state; call only after checking movement constraints."""
    score = state.score - 1
    coins, consumed = state.collected_coins, state.consumed
    fresh = position not in consumed
    if symbol == 'T':
        score -= 15
    elif fresh and symbol == 'C':
        score += 10
        coins = coins | {position}
    elif fresh and symbol == 'B':
        score += bonus
    if symbol in 'CKB':
        consumed = consumed | {position}
    return State(position, state.has_key or symbol == 'K', score, coins,
                 state.visited_cells | {position}, consumed)


class Environment:
    def __init__(self, grid, start, seed, hidden, bonuses):
        self.grid = grid
        self.rows, self.cols = len(grid), len(grid[0])
        self.seed, self.hidden, self.bonuses = seed, hidden, bonuses
        self.state = State(start, visited_cells=frozenset({start}))
        self.last_observation = None

    @classmethod
    def generate_world(cls, rows, cols, seed):
        if rows < 3 or cols < 3:
            raise ValueError('N, M нь 3-аас багагүй байна.')
        rng = random.Random(seed)
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        n = rows * cols
        symbols = ['.', 'K', 'E', '?', 'B'] + ['W'] * max(1, n // 6)
        symbols += ['C'] * max(1, n // 12) + ['T'] * max(1, n // 15)
        for _ in range(1000):
            rng.shuffle(cells)
            grid = [['.'] * cols for _ in range(rows)]
            for symbol, (r, c) in zip(symbols, cells):
                grid[r][c] = symbol
            world = cls(grid, cells[0], seed, rng.choice(['C', 'T', 'B', '.']),
                        {p: rng.randint(5, 20) for p in cells})
            kb = KnowledgeBase()
            kb.update_knowledge(world.percept())
            kb.infer()
            first = search(world.state, kb, cells[1], 'BFS')
            if first.found:
                second = search(first.states[-1], kb, cells[2], 'BFS')
                if second.found:
                    return world
        raise RuntimeError('Гарцтай талбай үүссэнгүй. Өөр seed/хэмжээ сонгоно уу.')

    def get_state(self):
        return self.state

    def percept(self):
        # Бүх газрын зураг харагдана; ?-ийн төрөл, бонусын хэмжээ нууц.
        visible = {}
        for r, row in enumerate(self.grid):
            for c, symbol in enumerate(row):
                p = (r, c)
                visible[p] = '.' if p in self.state.consumed else symbol
        return {'state': self.state, 'visible': visible,
                'last_observation': self.last_observation}

    def execute_action(self, action):
        dr, dc = DIRECTIONS[action]
        r, c = self.state.position
        p = (r + dr, c + dc)
        if not (0 <= p[0] < self.rows and 0 <= p[1] < self.cols):
            raise ValueError('Талбайн хилээс гарах үйлдэл')
        symbol = self.grid[p[0]][p[1]]
        if symbol == 'W' or (symbol == 'E' and not self.state.has_key):
            raise ValueError('Хориглосон хөдөлгөөн')
        if symbol == '?':
            symbol = self.hidden
            self.grid[p[0]][p[1]] = symbol
        self.last_observation = (p, symbol)
        self.state = transition(self.state, p, symbol, self.bonuses.get(p, 5))
        return 8 if symbol == 'T' else 1

    def board_text(self):
        visible = self.percept()['visible']
        return '\n'.join(' '.join('A' if (r, c) == self.state.position
                                  else visible[r, c] for c in range(self.cols))
                         for r in range(self.rows))


@dataclass(frozen=True)
class Rule:
    name: str
    premise: str
    conclusion: str
    match: object = None
    output: object = None

    def apply(self, fact):
        predicate, value = fact
        if predicate != self.premise:
            return None
        if self.match is not None and value != self.match:
            return None
        return (self.conclusion, value if self.output is None else self.output)


class KnowledgeBase:
    RULES = (
        Rule('R1', 'HasKey', 'Goal', False, 'Key'),
        Rule('R2', 'HasKey', 'Goal', True, 'Exit'),
        Rule('R3', 'Wall', 'NotTraversable'),
        Rule('R4', 'Trap', 'Dangerous'),
        Rule('R5', 'Dangerous', 'Avoid'),
        Rule('R6', 'Coin', 'PositiveUtility'),
        Rule('R7', 'Bonus', 'PositiveUtility'),
    )

    def __init__(self):
        self.facts = set()
        self.visible = {}
        self.state = None
        self.inferences = []

    def update_knowledge(self, percept):
        old = self.facts.copy()
        self.state, self.visible = percept['state'], dict(percept['visible'])
        # Rebuild current facts: retract obsolete HasKey/Unknown/Goal facts.
        self.facts = {(NAMES[s], p) for p, s in self.visible.items()}
        self.facts.update({('At', self.state.position), ('HasKey', self.state.has_key)})
        self.facts.update(('Visited', p) for p in self.state.visited_cells)
        if percept['last_observation'] is not None:
            position, symbol = percept['last_observation']
            self.facts.add(('Observed' + NAMES[symbol], position))
        return self.facts - old, old - self.facts

    def infer(self):
        self.inferences = []
        while True:
            additions = set()
            for rule in self.RULES:
                for fact in sorted(self.facts, key=repr):
                    result = rule.apply(fact)
                    if result is not None and result not in self.facts | additions:
                        additions.add(result)
                        self.inferences.append(f'{rule.name}: {fact} -> {result}')
            if not additions:
                return
            self.facts.update(additions)

    def choose_goal(self):
        kind = 'Exit' if ('Goal', 'Exit') in self.facts else 'Key'
        locations = sorted(value for predicate, value in self.facts if predicate == kind)
        return kind, locations[0] if locations else None

    def cost(self, position):
        # Reasoning output directly affects A* path cost.
        return 8 if ('Avoid', position) in self.facts else 1


def get_successors(state, kb):
    for action, (dr, dc) in DIRECTIONS.items():
        p = (state.position[0] + dr, state.position[1] + dc)
        if p not in kb.visible or ('NotTraversable', p) in kb.facts:
            continue
        symbol = kb.visible[p]
        if symbol == 'E' and not state.has_key:
            continue
        # Unknown is assumed cost=1 until observed, never read hidden world data.
        yield action, transition(state, p, symbol), kb.cost(p)


def goal_test(state, goal, kb):
    return state.position == goal and (kb.visible[goal] != 'E' or state.has_key)


def heuristic(position, goal):
    return abs(position[0] - goal[0]) + abs(position[1] - goal[1])


@dataclass
class SearchResult:
    found: bool
    actions: list
    states: list
    cost: int
    expanded: int
    seconds: float


def search(initial, kb, goal, algorithm):
    """BFS / A*. Full State nodes, projected duplicate key (position, has_key).

    Score/coins/visited do not affect legal moves, goal, or path costs here.
    Therefore higher-cost paths to the same projected key can be discarded.
    This optimization would be invalid if score/coin goals were introduced.
    """
    if algorithm not in ('BFS', 'A*'):
        raise ValueError('Algorithm must be BFS or A*')
    started = perf_counter()
    if goal is None or goal not in kb.visible:
        return SearchResult(False, [], [], 0, 0, perf_counter() - started)
    serial = count()
    # Node: (state, parent index, action, actual weighted cost, depth)
    nodes = [(initial, None, None, 0, 0)]
    queue = deque([0])
    heap = [(heuristic(initial.position, goal), next(serial), 0)]
    best = {(initial.position, initial.has_key): 0}
    expanded = 0
    while queue if algorithm == 'BFS' else heap:
        index = queue.popleft() if algorithm == 'BFS' else heapq.heappop(heap)[2]
        state, parent, action, cost, depth = nodes[index]
        key = (state.position, state.has_key)
        objective = depth if algorithm == 'BFS' else cost
        if objective != best[key]:
            continue
        if goal_test(state, goal, kb):
            actions, states = [], []
            cursor = index
            while cursor is not None:
                s, parent, a, _, _ = nodes[cursor]
                states.append(s)
                if a is not None:
                    actions.append(a)
                cursor = parent
            return SearchResult(True, actions[::-1], states[::-1], cost,
                                expanded, perf_counter() - started)
        expanded += 1  # A node counts when its successors are generated.
        for a, successor, step_cost in get_successors(state, kb):
            g, d = cost + step_cost, depth + 1
            metric = d if algorithm == 'BFS' else g
            key2 = (successor.position, successor.has_key)
            if metric >= best.get(key2, float('inf')):
                continue
            best[key2] = metric
            child = len(nodes)
            nodes.append((successor, index, a, g, d))
            if algorithm == 'BFS':
                queue.append(child)
            else:
                heapq.heappush(heap, (g + heuristic(successor.position, goal),
                                      next(serial), child))
    return SearchResult(False, [], [], 0, expanded, perf_counter() - started)


class IntelligentAgent:
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.kb = KnowledgeBase()

    def program(self, percept):
        added, removed = self.kb.update_knowledge(percept)
        self.kb.infer()
        kind, goal = self.kb.choose_goal()
        result = search(percept['state'], self.kb, goal, self.algorithm)
        explanation = [f'PERCEPT state={percept["state"]}',
                       f'Visible={sorted(self.kb.visible.items())}',
                       f'Observation={percept["last_observation"]}',
                       f'NEW FACTS={sorted(added, key=repr)}',
                       f'RETRACTED FACTS={sorted(removed, key=repr)}',
                       'INFERENCE\n' + '\n'.join(self.kb.inferences),
                       f'GOAL={kind} {goal}',
                       f'SEARCH={self.algorithm}, found={result.found}, '
                       f'expanded={result.expanded}, planned_cost={result.cost}, '
                       f'search_seconds={result.seconds:.9f}',
                       f'PLAN={[s.position for s in result.states]}']
        action = result.actions[0] if result.actions else None
        explanation.append(f'ACTION={action}')
        explanation.append('REASON=' + ('Хамгийн цөөн алхамтай замын эхний үйлдэл.'
                           if self.algorithm == 'BFS' else
                           'Мэдэгдэж буй эрсдэлийн өртөг хамгийн бага замын эхний үйлдэл.'))
        return action, result, '\n'.join(explanation)


def run_agent(world, algorithm, explain=False):
    agent = IntelligentAgent(algorithm)
    logs = [f'ALGORITHM={algorithm}\nINITIAL BOARD\n{world.board_text()}']
    steps = expanded = cost = searches = traps = 0
    search_seconds = 0.0
    started = perf_counter()
    status = 'STEP_LIMIT'
    # Safety limit; normally each fixed-map phase follows a shortest path.
    for _ in range(world.rows * world.cols * 4):
        s = world.state
        if s.has_key and world.grid[s.position[0]][s.position[1]] == 'E':
            status = 'REACHED'
            break
        action, result, explanation = agent.program(world.percept())
        logs.append(f'\nSTEP {steps + 1}\n{explanation}')
        if explain:
            print(f'\n[{algorithm}] STEP {steps + 1}\n{world.board_text()}\n{explanation}')
        searches += 1
        expanded += result.expanded
        search_seconds += result.seconds
        if not result.found or action is None:
            status = 'SEARCH_FAILURE'
            break
        edge = world.execute_action(action)
        cost += edge
        traps += edge == 8
        steps += 1
        logs.append(f'AFTER ACTION={world.state}\nOBSERVED={world.last_observation}\nACTUAL COST={edge}')
    # Record terminal percept, including the last observation and new goal facts.
    added, removed = agent.kb.update_knowledge(world.percept())
    agent.kb.infer()
    logs.append(f'FINAL PERCEPT={world.percept()}\nNEW FACTS={sorted(added, key=repr)}\n'
                f'RETRACTED FACTS={sorted(removed, key=repr)}\n'
                + '\n'.join(agent.kb.inferences))
    s = world.state
    reached = s.has_key and world.grid[s.position[0]][s.position[1]] == 'E'
    if reached:
        status = 'REACHED'
    metrics = dict(algorithm=algorithm, path_length=steps, expanded_nodes=expanded,
                   total_path_cost=cost, search_seconds=search_seconds,
                   execution_seconds=perf_counter() - started, goal_reached=reached,
                   score=s.score, coins=len(s.collected_coins), traps=traps,
                   unique_cells=len(s.visited_cells), searches=searches, status=status)
    logs.append('RESULT=' + json.dumps(metrics, ensure_ascii=False))
    return metrics, '\n'.join(logs), agent


def read_int(prompt, minimum=None):
    while True:
        try:
            value = int(input(prompt))
            if minimum is not None and value < minimum:
                raise ValueError
            return value
        except ValueError:
            print('Зөв бүхэл тоо оруулна уу.' + (f' Доод утга: {minimum}' if minimum else ''))


def main():
    parser = argparse.ArgumentParser(description='Smart Escape II - BFS ба A*')
    parser.add_argument('--rows', type=int)
    parser.add_argument('--cols', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--explain', action='store_true', help='Алхам бүрийн үндэслэлийг харуулах')
    args = parser.parse_args()
    rows = args.rows if args.rows is not None else read_int('Мөр N (>=3): ', 3)
    cols = args.cols if args.cols is not None else read_int('Багана M (>=3): ', 3)
    seed = args.seed if args.seed is not None else read_int('Seed: ')
    try:
        base = Environment.generate_world(rows, cols, seed)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(f'Оюутан: {STUDENT_ID}\nSeed: {seed}\n{base.board_text()}')
    results, logs = [], []
    for algorithm in ('BFS', 'A*'):
        metrics, log, _ = run_agent(copy.deepcopy(base), algorithm, args.explain)
        results.append(metrics)
        logs.append(log)
    out = Path(__file__).resolve().parent / 'results'
    out.mkdir(exist_ok=True)
    prefix = f'{STUDENT_ID}_{seed}'
    reasoning = out / f'{prefix}_reasoning.txt'
    reasoning.write_text(f'STUDENT={STUDENT_ID}\nSEED={seed}\nSIZE={rows}x{cols}\n'
                         + '\n\n'.join(logs), encoding='utf-8')
    comparison = out / f'{prefix}_comparison.csv'
    with comparison.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print('\nAlgorithm  Length  Expanded  Cost  Search(ms)  Reached  Score')
    for m in results:
        print(f'{m["algorithm"]:9} {m["path_length"]:6} {m["expanded_nodes"]:9} '
              f'{m["total_path_cost"]:5} {m["search_seconds"]*1000:11.3f} '
              f'{str(m["goal_reached"]):8} {m["score"]}')
    print(f'\nЛог: {reasoning}\nХарьцуулалт: {comparison}')


if __name__ == '__main__':
    main()
