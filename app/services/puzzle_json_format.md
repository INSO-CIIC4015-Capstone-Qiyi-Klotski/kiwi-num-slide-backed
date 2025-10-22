# 🧮 Puzzle JSON Format (Example Explanation)

When the backend sends a puzzle, **everything comes in flat lists** (`numbers`, `operators`, `expected`).
The frontend must reconstruct the grid using the given value of `N`.

---

## 🧩 Example with N = 3

```json
{
  "N": 3,
  "numbers": [1, 4, 5, 3, 8, 1, 2, 5, 2],
  "operators": ["+1", "-2", "+3", "+4", "+5", "-6", "-7", "+8", "+9", "-10", "+11", "-12"],
  "expected": ["10", "5", "8", "10", "9", "4"]
}
```

---

## 🔍 Visual Representation with Operator IDs

```
                                  expected
     1    +1    4    -2    5        -> 10
     
    -7         +8         +9
    
     3    +3    8    +4    1        -> 5
     
   -10        -11         -12
   
     2    +5    5    -6    2        -> 8
     
     |          |          |
     v          v          v
     10         9          4
```

---

## 🟢 Explanation

- **numbers** always comes as a flat list of length **N × N**, filled row by row.

  ```
  [1,4,5]
  [3,8,1]
  [2,5,2]
  ```

  > The empty tile is always represented by the number **1** in this list. There are no repeated `1`s — only one blank space exists per puzzle.

- **operators** always comes with **2 × N × (N − 1)** elements:

  - The **first half** are **horizontal operators** (row by row).
  - The **second half** are **vertical operators** (column by column).

- **expected** always comes with **2 × N** elements:

  - The **first N** correspond to **row results (→)**.
  - The **last N** correspond to **column results (↓)**.

---

## 📏 General Rules

| Field | Count | Description |
|-------|--------|-------------|
| `numbers` | N × N | Board numbers (flat). The blank tile is represented as 1. |
| `operators` | 2 × N × (N − 1) | first half = rows, second half = columns |
| `expected` | 2 × N | first half = row results, second half = column results |

---

✅ **Frontend Tip:**  
1. Split numbers into rows of N elements.

2. Take the first N*(N-1) operators for horizontal placement.

3. Use the remaining operators for vertical placement.

4. Display expected values — first N on the right of each row from top to bottom, last N below each column from left to right.
