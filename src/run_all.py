"""Regenerate every data file behind the webpage.

Run from the project root:  python src/run_all.py
"""
import q1_overview
import q2_priorities
import q3_risks

if __name__ == "__main__":
    for module in (q1_overview, q2_priorities, q3_risks):
        print(f"\n===== {module.__name__} =====")
        module.main()
