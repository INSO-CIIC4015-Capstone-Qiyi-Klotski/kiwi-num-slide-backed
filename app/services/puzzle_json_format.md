# 🧮 Puzzle JSON Format (Example Explanation)

When the backend sends a puzzle, **everything comes in flat lists** (`numbers`, `operators`, `expected`).
The frontend must reconstruct the grid using the given value of `N`.

---

## 🧩 Example with N = 3

```json
{
  "N": 3,
  "numbers": [3, 2, 4, 2, 2, 2, 4, 3],
  "operators": ["+1", "-2", "+3", "+4", "*5", "-6", "*7", "-8", "-9", "-10"],
  "expected": ["1", "6", "1", "11", "1", "2"]
}
```

---

## 🔍 Visual Representation with Operator IDs

```
                                  expected
     3    +1    2    -2     4        -> 1

     +3         *4         -5

     2    +6    2    *7     2        -> 6

     *8        -9

     4    -10   3                    -> 1

     |          |           |
     v          v           v
     11         1           2
```

---

## 🟢 Explanation

- **numbers** always comes as a flat list of length **N × N - 1**, filled row by row.

  ```
  [1,4,5]
  [3,8,1]
  [2,5, ]
  ```

- **operators** always comes with **2 × N × (N − 1) - 2** elements:

  - The **first half** are **horizontal operators** (row by row).
  - The **second half** are **vertical operators** (column by column).

- **expected** always comes with **2 × N** elements:

  - The **first N** correspond to **row results (→)**.
  - The **last N** correspond to **column results (↓)**.

---

## 📏 General Rules

| Field | Count               | Description |
|-------|---------------------|-------------|
| `numbers` | N × N - 1           | Board numbers (flat). The blank tile is represented as 1. |
| `operators` | 2 × N × (N − 1) - 2 | first half = rows, second half = columns |
| `expected` | 2 × N               | first half = row results, second half = column results |

---

✅ **Frontend Tip:**  
1. Split the numbers into rows of N elements.

2. The operators in the flat list are interleaved — first come the ones placed between columns in the first row, followed by the operators that go between rows connecting that row to the next one.

3. This pattern continues alternating: operators between columns, then operators between rows, until the end of the list, which finishes with the between-columns operators of the last row.

4. Display the expected values as follows: the first N go to the right of each row (top to bottom), and the last N go below each column (left to right).
