import random
from collections import deque
from pathlib import Path


STUDENT_ID = "B242270129"

# Команд: (мөрийн өөрчлөлт, баганын өөрчлөлт, нэр)
DIRECTIONS = {
    "W": (-1, 0, "ДЭЭШ"),
    "S": (1, 0, "ДООШ"),
    "A": (0, -1, "ЗҮҮН"),
    "D": (0, 1, "БАРУУН"),
}

OBJECT_NAMES = {
    ".": "Хоосон нүд",
    "K": "Түлхүүр",
    "E": "Гарах хаалга",
    "C": "Зоос",
    "T": "Хавх",
    "B": "Нэмэлт оноо",
}


def read_integer(message, minimum=None):
    while True:
        try:
            value = int(input(message))
            if minimum is not None and value < minimum:
                print(f"{minimum}-аас багагүй тоо оруулна уу.")
                continue
            return value
        except ValueError:
            print("Бүхэл тоо оруулна уу.")


class Object:
    """Орчинд байрлах объектын суурь класс."""

    def __init__(self, symbol, location):
        self.symbol = symbol
        self.location = location

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.symbol}>"

    def is_alive(self):
        return getattr(self, "alive", False)


class Agent(Object):
    """Тоглогчийн төлөв болон үйлдэл сонгох хэсэг."""

    def __init__(self, location):
        super().__init__("P", location)
        self.alive = True
        self.performance = 100
        self.steps = 0
        self.has_key = False
        self.coins = 0
        self.traps = 0
        self.hints = 0
        self.visited = {location}
        self.revisits = 0
        self.escaped = False

    def program(self, percept):
        print(percept)
        return input("Команд [W/S/A/D/H/Q]: ").strip().upper()


class Environment:
    """Орчин, агент болон тоглоомын дүрмийг удирдана."""

    def __init__(self, rows, cols, seed):
        self.rows = rows
        self.cols = cols
        self.seed = seed
        self.rng = random.Random(seed)
        self.objects = []
        self.logs = []
        self.log_path = (
            Path(__file__).resolve().parent
            / f"{STUDENT_ID}_{seed}_log.txt"
        )

        self.generate_world()
        self.add_log(
            f"Оюутны код: {STUDENT_ID}\n"
            f"Seed: {seed}\n"
            f"Талбай: {rows} x {cols}\n"
            f"Эхлэх байрлал: {self.agent.location}\n"
            f"Эхлэх оноо: {self.agent.performance}\n"
            f"Эхний талбай:\n{self.board_text()}"
        )

    def inside(self, location):
        row, col = location
        return 0 <= row < self.rows and 0 <= col < self.cols

    def cell(self, location):
        row, col = location
        return self.grid[row][col]

    def distance(self, start, goal, has_key):
        """BFS: хана болон түгжээтэй хаалгыг тойрох хамгийн богино зай."""
        queue = deque([(start, 0)])
        seen = {start}

        while queue:
            current, steps = queue.popleft()

            if current == goal:
                return steps

            for dr, dc, _ in DIRECTIONS.values():
                next_pos = (current[0] + dr, current[1] + dc)

                if not self.inside(next_pos) or next_pos in seen:
                    continue

                symbol = self.cell(next_pos)
                if symbol == "W":
                    continue
                if symbol == "E" and not has_key:
                    continue

                seen.add(next_pos)
                queue.append((next_pos, steps + 1))

        return None

    def generate_world(self):
        """Seed-ээр байрлуулж, гарцтай эсэхийг шалгана."""
        positions = [
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
        ]

        total = self.rows * self.cols
        wall_count = max(1, total // 6)
        coin_count = max(1, total // 12)
        trap_count = max(1, total // 15)

        # P, K, E, ?, B болон бусад объектууд тусдаа нүд эзэлнэ.
        symbols = (
            ["P", "K", "E", "?", "B"]
            + ["W"] * wall_count
            + ["C"] * coin_count
            + ["T"] * trap_count
        )

        for _ in range(1000):
            self.grid = [
                ["."] * self.cols for _ in range(self.rows)
            ]
            self.rng.shuffle(positions)
            placed = list(zip(symbols, positions))

            for symbol, (row, col) in placed:
                self.grid[row][col] = symbol

            start = positions[0]
            self.key_position = positions[1]
            self.exit_position = positions[2]

            # Тоглогчийг талбайн тэмдэгтээс тусад нь хадгална.
            self.grid[start[0]][start[1]] = "."

            to_key = self.distance(
                start, self.key_position, has_key=False
            )
            to_exit = self.distance(
                self.key_position, self.exit_position, has_key=True
            )

            if to_key is not None and to_exit is not None:
                self.agent = Agent(start)
                self.objects = [
                    Object(symbol, location)
                    for symbol, location in placed
                    if symbol != "P"
                ]
                self.objects.append(self.agent)

                # Энэ утгыг зөвлөмжид ашиглахгүй.
                self.hidden_object = self.rng.choice(
                    ["C", "T", "B", "."]
                )
                return

        raise RuntimeError(
            "1000 оролдлогоор гарцтай талбай үүссэнгүй. "
            "Өөр seed эсвэл талбайн хэмжээ ашиглана уу."
        )

    def board_text(self):
        lines = []

        for row in range(self.rows):
            line = []
            for col in range(self.cols):
                if (row, col) == self.agent.location:
                    line.append("P")
                else:
                    line.append(self.grid[row][col])
            lines.append(" ".join(line))

        return "\n".join(lines)

    def display_world(self):
        print("\n" + self.board_text())
        print(
            "P=Тоглогч  E=Гарц  K=Түлхүүр  W=Хана\n"
            "C=Зоос  T=Хавх  B=Бонус  ?=Үл мэдэгдэх  .=Хоосон"
        )

    def percept(self, agent):
        key_status = "Тийм" if agent.has_key else "Үгүй"
        return (
            f"\nБайрлал: {agent.location} | "
            f"Оноо: {agent.performance} | "
            f"Алхам: {agent.steps} | "
            f"Түлхүүр: {key_status}"
        )

    def get_possible_moves(self):
        possible = {}
        row, col = self.agent.location

        for command, (dr, dc, _) in DIRECTIONS.items():
            location = (row + dr, col + dc)

            if not self.inside(location):
                possible[command] = (None, "Талбайн хил")
            elif self.cell(location) == "W":
                possible[command] = (None, "Хана")
            elif self.cell(location) == "E" and not self.agent.has_key:
                possible[command] = (None, "Түлхүүр аваагүй")
            else:
                possible[command] = (location, "")

        return possible

    def consume_object(self, location):
        """Авсан объект талбайгаас болон объектын жагсаалтаас арилна."""
        row, col = location
        self.grid[row][col] = "."
        self.objects = [
            obj for obj in self.objects
            if obj is self.agent or obj.location != location
        ]

    def process_cell(self):
        agent = self.agent
        symbol = self.cell(agent.location)
        prefix = ""

        if symbol == "?":
            symbol = self.hidden_object
            prefix = "? илэрлээ → "

        message = prefix + OBJECT_NAMES.get(symbol, symbol)

        if symbol == "K":
            agent.has_key = True
        elif symbol == "C":
            agent.coins += 1
            agent.performance += 10
            message += " (+10 оноо)"
        elif symbol == "T":
            agent.traps += 1
            agent.performance -= 15
            message += " (-15 оноо)"
        elif symbol == "B":
            bonus = self.rng.randint(5, 20)
            agent.performance += bonus
            message += f" (+{bonus} оноо)"
        elif symbol == "E":
            agent.escaped = True
            agent.alive = False
            message = "Түлхүүртэйгээр гарцад хүрлээ!"

        # Хавхыг хэвээр үлдээнэ: дахин гишгэвэл дахин -15.
        if symbol == "T":
            row, col = agent.location
            self.grid[row][col] = "T"
            for obj in self.objects:
                if obj is not agent and obj.location == agent.location:
                    obj.symbol = "T"
        elif symbol != "E":
            self.consume_object(agent.location)

        return message

    def move_player(self, command):
        location, reason = self.get_possible_moves()[command]

        if location is None:
            message = f"{command}: хөдөлж болохгүй — {reason}."
            print(message)
            self.add_log(message + "\n" + self.percept(self.agent))
            return

        agent = self.agent
        previous = agent.location
        agent.location = location
        agent.steps += 1
        agent.performance -= 1

        if location in agent.visited:
            agent.revisits += 1
        agent.visited.add(location)

        message = self.process_cell()
        print(message)

        self.add_log(
            f"Алхам: {agent.steps}\n"
            f"Байрлал: {previous} → {location}\n"
            f"Үйлдэл: {command}\n"
            f"Объект: {message}\n"
            f"Оноо: {agent.performance}"
        )

    def evaluate_move(self, location):
        """Зай, хавх, шагнал, өмнө очсон эсэхээр үнэлнэ."""
        agent = self.agent
        goal = (
            self.exit_position if agent.has_key
            else self.key_position
        )

        distance = self.distance(
            location, goal, has_key=agent.has_key
        )

        if distance is None:
            return -10000, "Зорилтод хүрэх замгүй"

        symbol = self.cell(location)
        score = -3 * distance
        details = [f"зай={distance}: {-3 * distance}"]

        if symbol == "T":
            score -= 15
            details.append("хавх: -15")
        elif symbol == "C":
            score += 10
            details.append("зоос: +10")
        elif symbol == "B":
            score += 5
            details.append("бонус: +5")

        if location in agent.visited:
            score -= 6
            details.append("өмнө очсон: -6")

        if location == goal:
            score += 30
            details.append("зорилт: +30")

        # ? доторх нууц төрлийг энд шалгахгүй.
        return score, ", ".join(details)

    def get_hint(self):
        self.agent.hints += 1
        lines = ["=== Ухаалаг зөвлөмж ==="]
        best_command = None
        best_score = float("-inf")

        for command, (location, reason) in self.get_possible_moves().items():
            name = DIRECTIONS[command][2]

            if location is None:
                lines.append(f"{name}: боломжгүй ({reason})")
                continue

            score, explanation = self.evaluate_move(location)
            lines.append(f"{name}: {score} ({explanation})")

            if score > best_score:
                best_score = score
                best_command = command

        if best_command is None:
            lines.append("Боломжит хөдөлгөөн алга.")
        else:
            name = DIRECTIONS[best_command][2]
            lines.append(
                f"Санал болгож буй хөдөлгөөн: {name} ({best_command})"
            )

        text = "\n".join(lines)
        print(text)
        self.add_log(self.percept(self.agent) + "\n" + text)

    def execute_action(self, agent, action):
        if action in DIRECTIONS:
            self.move_player(action)
        elif action == "H":
            self.get_hint()
        elif action == "Q":
            agent.alive = False
            self.add_log("Үйлдэл: Q — хэрэглэгч тоглоомыг зогсоов.")
        else:
            print("Буруу команд. W/S/A/D/H/Q ашиглана уу.")
            self.add_log(f"Буруу команд: {action!r}")

    def add_log(self, message):
        self.logs.append(message)

    def save_log(self):
        try:
            self.log_path.write_text(
                "\n\n".join(self.logs) + "\n",
                encoding="utf-8",
            )
            print(f"\nЛог хадгаллаа: {self.log_path}")
        except OSError as error:
            print(f"\nЛог хадгалж чадсангүй: {error}")

    def show_result(self):
        agent = self.agent
        result = "ГАРСАН" if agent.escaped else "ЗОГСООСОН"
        key_status = "Тийм" if agent.has_key else "Үгүй"

        text = (
            "\n========== ҮР ДҮН ==========\n"
            f"Оюутны код       : {STUDENT_ID}\n"
            f"Seed             : {self.seed}\n"
            f"Алхам            : {agent.steps}\n"
            f"Явсан нүд        : {len(agent.visited)}\n"
            f"Давтан орсон тоо : {agent.revisits}\n"
            f"Зоос             : {agent.coins}\n"
            f"Хавх             : {agent.traps}\n"
            f"Зөвлөмж          : {agent.hints}\n"
            f"Түлхүүр олсон    : {key_status}\n"
            f"Эцсийн оноо      : {agent.performance}\n"
            f"Үр дүн           : {result}\n"
            "Явсан нүдэнд эхлэх нүдийг оруулж тооцов."
        )
        print(text)
        self.add_log(text)

    def run(self):
        try:
            while self.agent.is_alive():
                self.display_world()
                action = self.agent.program(self.percept(self.agent))
                self.execute_action(self.agent, action)
        except (KeyboardInterrupt, EOFError):
            self.agent.alive = False
            print("\nТоглоомыг зогсоолоо.")
            self.add_log("Оролт тасарсан тул тоглоомыг зогсоов.")
        finally:
            self.show_result()
            self.save_log()


def main():
    print("=== Smart Escape — Ухаалаг гарц ===")
    print(f"Оюутны код: {STUDENT_ID}")

    rows = read_integer("Мөрийн тоо N: ", minimum=3)
    cols = read_integer("Баганын тоо M: ", minimum=3)
    seed = read_integer("Seed: ")

    try:
        game = Environment(rows, cols, seed)
    except RuntimeError as error:
        print(error)
        return

    game.run()


if __name__ == "__main__":
    main()
