def find_unmatched_braces(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        stack = []
        for i, line in enumerate(f, 1):
            for j, char in enumerate(line, 1):
                if char == '{':
                    stack.append((i, j))
                elif char == '}':
                    if not stack:
                        print(f"Unmatched '}}' at line {i}, col {j}")
                    else:
                        stack.pop()
        for i, j in stack:
            print(f"Unmatched '{{' at line {i}, col {j}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(current_dir, 'fifo_calculator.py')
    find_unmatched_braces(target)
