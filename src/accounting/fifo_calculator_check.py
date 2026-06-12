import tokenize

def check_syntax(filename):
    try:
        with open(filename, 'rb') as f:
            for token in tokenize.tokenize(f.readline):
                pass
        print("Syntax is OK")
    except Exception as e:
        print(f"Syntax error: {e}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(current_dir, 'fifo_calculator.py')
    check_syntax(target)
