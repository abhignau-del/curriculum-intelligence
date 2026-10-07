"""Write the fictional sample programmes in backend/samples/.

All institutions are invented. Course content is typical of Indian B.Sc.
Mathematics syllabi but copied from no real one. Run from backend/:

    python tools/make_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from curintel.schema import Course, Programme, save_programme  # noqa: E402

# key: (title, credits, topics)
LIBRARY: dict[str, tuple[str, float, list[str]]] = {
    "calc1": ("Calculus", 4, [
        "Limits and continuity", "Differentiability and mean value theorems",
        "Successive differentiation, Leibniz rule", "Taylor's theorem and Maclaurin series",
        "Maxima and minima of functions of one variable", "Curve tracing"]),
    "multivariable": ("Multivariable Calculus", 4, [
        "Functions of several variables, partial derivatives", "Jacobians and change of variables",
        "Maxima and minima, Lagrange multipliers", "Double and triple integrals",
        "Change of order of integration"]),
    "vector": ("Vector Calculus", 4, [
        "Vector differentiation", "Gradient, divergence and curl",
        "Line integrals, surface integrals and volume integrals", "Green's theorem in the plane",
        "Stokes's theorem and Gauss divergence theorem"]),
    "real1": ("Real Analysis I", 4, [
        "Real number system, completeness property", "Sequences of real numbers, Cauchy sequences",
        "Convergence of series, comparison and ratio tests", "Continuity and uniform continuity"]),
    "real2": ("Real Analysis II", 4, [
        "Riemann integration", "Uniform convergence of sequences and series of functions",
        "Power series", "Improper integrals"]),
    "linalg": ("Linear Algebra", 4, [
        "Vector spaces, subspaces, basis and dimension", "Linear transformations, rank-nullity theorem",
        "Matrix of a linear transformation", "Eigenvalues and eigenvectors, diagonalisation",
        "Inner product spaces, Gram-Schmidt process"]),
    "algebra1": ("Group Theory", 4, [
        "Groups, subgroups and cyclic groups", "Permutation groups", "Cosets and Lagrange's theorem",
        "Normal subgroups and quotient groups", "Homomorphisms and isomorphism theorems"]),
    "algebra2": ("Ring Theory", 4, [
        "Rings, integral domains and fields", "Ideals and quotient rings", "Ring homomorphisms",
        "Polynomial rings"]),
    "complex": ("Complex Analysis", 4, [
        "Analytic functions, Cauchy-Riemann equations", "Contour integration, Cauchy's integral formula",
        "Laurent series", "Residue theorem and its applications", "Conformal mapping"]),
    "topology": ("Topology", 4, [
        "Topological spaces, open sets and bases", "Continuity and homeomorphism", "Compactness",
        "Connectedness"]),
    "metric": ("Metric Spaces", 4, [
        "Metric spaces, open and closed sets", "Complete metric spaces",
        "Contraction mapping, Banach fixed point theorem", "Compactness in metric spaces"]),
    "ode": ("Ordinary Differential Equations", 4, [
        "First order equations, exact equations", "Linear differential equations with constant coefficients",
        "Wronskian and variation of parameters", "Series solutions", "Initial value problems"]),
    "pde": ("Partial Differential Equations", 4, [
        "Formation of partial differential equations", "Lagrange's method", "Charpit's method",
        "Classification of second order equations",
        "Heat equation, wave equation and Laplace equation by separation of variables"]),
    "mechanics": ("Mechanics", 4, [
        "Statics: equilibrium of forces", "Kinematics in one and two dimensions", "Projectile motion",
        "Central forces", "Simple harmonic motion"]),
    "numerical": ("Numerical Methods", 4, [
        "Errors and error analysis", "Root finding: bisection method, Newton-Raphson method",
        "Interpolation", "Numerical differentiation and numerical integration: trapezoidal rule, Simpson's rule",
        "Numerical solution of ODE: Euler's method, Runge-Kutta methods"]),
    "numerical_lab": ("Numerical Methods Lab (Python)", 2, [
        "Implementing bisection and Newton-Raphson in Python", "Interpolation using NumPy",
        "Numerical integration with SciPy", "Plotting solutions with Matplotlib"]),
    "numerical_lab_c": ("Numerical Methods Lab (C)", 2, [
        "Programming in C: bisection and Newton-Raphson", "Gauss-Seidel iteration",
        "Trapezoidal rule and Simpson's rule programs"]),
    "prob": ("Probability Theory", 4, [
        "Axioms of probability, conditional probability, Bayes theorem",
        "Random variables and mathematical expectation", "Binomial, Poisson and normal distribution",
        "Moment generating function", "Central limit theorem"]),
    "stats": ("Statistical Methods", 4, [
        "Measures of central tendency and dispersion", "Skewness and kurtosis", "Correlation and regression",
        "Probability distributions: binomial, Poisson and normal", "Tests of significance: t test, chi square test"]),
    "inference": ("Statistical Inference", 4, [
        "Sampling distribution", "Point estimation, maximum likelihood", "Confidence intervals",
        "Testing of hypotheses", "Analysis of variance"]),
    "lp": ("Linear Programming", 4, [
        "Formulation of linear programming problems", "Simplex method", "Duality",
        "Transportation problem", "Assignment problem"]),
    "or": ("Operations Research", 4, [
        "Queueing theory", "Game theory", "Inventory models", "PERT and CPM project scheduling"]),
    "modelling": ("Mathematical Modelling", 4, [
        "Model formulation and validation", "Population models and logistic growth", "Predator-prey models",
        "Epidemic models: the SIR model", "Modelling with difference equations"]),
    "python": ("Programming with Python", 4, [
        "Python basics: variables, control flow and functions", "Lists and dictionaries", "NumPy arrays",
        "Plotting with Matplotlib", "SymPy for symbolic computation"]),
    "c_prog": ("Programming in C", 4, [
        "Algorithms and flowcharts", "C programming: data types and control structures",
        "Arrays and functions", "Pointers and structures"]),
    "data": ("Data Analysis with Python", 4, [
        "Data handling with pandas", "Exploratory data analysis", "Data visualisation with Matplotlib",
        "Working with a real world dataset", "Descriptive statistics in Python"]),
    "ml": ("Introduction to Machine Learning", 4, [
        "Supervised learning: linear and logistic regression", "Decision trees",
        "Unsupervised learning: k-means clustering", "Gradient descent", "Model evaluation"]),
    "r_stats": ("Statistical Computing with R", 2, [
        "R programming basics", "Data visualisation using ggplot2", "Hypothesis testing in R software",
        "Regression analysis in R"]),
    "number": ("Number Theory", 4, [
        "Divisibility and the Euclidean algorithm", "Prime numbers", "Congruences, Chinese remainder theorem",
        "Fermat's little theorem and Euler's totient function", "Quadratic residues"]),
    "discrete": ("Discrete Mathematics", 4, [
        "Propositional logic", "Set theory and relations", "Mathematical induction",
        "Permutations and combinations, pigeonhole principle", "Recurrence relations and generating functions"]),
    "graph": ("Graph Theory", 4, [
        "Graphs, paths and cycles", "Trees and connectivity, spanning trees",
        "Eulerian graphs and Hamiltonian graphs", "Planar graphs", "Graph colouring",
        "Shortest path algorithms"]),
    "transforms": ("Integral Transforms", 4, [
        "Laplace transform and inverse Laplace transform", "Convolution theorem", "Fourier series",
        "Fourier transform", "Applications to differential equations"]),
    "diffgeo": ("Differential Geometry", 4, [
        "Curves in space, Serret-Frenet formulae", "Curvature and torsion",
        "Surfaces and the first fundamental form", "Geodesics"]),
    "functional": ("Functional Analysis", 4, [
        "Normed linear spaces", "Banach spaces", "Hilbert spaces", "Bounded linear operators",
        "Hahn-Banach theorem"]),
    "finance": ("Financial Mathematics", 4, [
        "Compound interest and present value", "Annuities", "Portfolio theory",
        "Option pricing and the Black-Scholes model"]),
    "crypto": ("Cryptography", 4, [
        "Classical ciphers", "Modular arithmetic", "RSA public key cryptography", "Coding theory basics"]),
    "stochastic": ("Stochastic Processes", 4, [
        "Markov chains", "Random walk", "Poisson process", "Birth and death process"]),
    "timeseries": ("Time Series and Forecasting", 4, [
        "Components of a time series, trend analysis", "Moving averages", "Seasonal variation",
        "ARIMA models", "Forecasting"]),
    "latex": ("Mathematical Typesetting with LaTeX", 2, [
        "Document structure in LaTeX", "Typesetting equations", "Beamer presentations",
        "Technical writing"]),
    "history": ("History of Mathematics", 2, [
        "Indian mathematics: Aryabhata, Brahmagupta and Bhaskara", "The Kerala school",
        "Greek mathematics", "Development of calculus"]),
    "project": ("Project / Dissertation", 6, [
        "Research methodology", "Literature review", "Dissertation and viva voce"]),
    "internship": ("Internship", 4, [
        "Internship of four weeks", "Report writing and presentation"]),
    "sci_comp": ("Scientific Computing", 4, [
        "Scientific computing with Python", "Monte Carlo simulation",
        "Numerical solution of ODE using SciPy", "Visualisation of results"]),
    "sql": ("Databases for Data Science", 4, [
        "Relational database concepts", "SQL queries", "Data cleaning"]),
    "excel": ("Spreadsheet Modelling", 2, [
        "Spreadsheet functions in MS Excel", "Charts and dashboards", "What-if analysis"]),
    "seminar": ("Seminar", 2, ["Seminar presentation", "Mathematical writing"]),
}

# Courses only the programme under review has. Two pairs overlap on purpose:
# Calculus II repeats much of Vector Calculus, and Statistical Methods repeats
# Probability and Statistics.
OWN_EXTRA = {
    "calc2": ("Calculus II", 4, [
        "Functions of several variables, partial derivatives", "Double and triple integrals",
        "Gradient, divergence and curl", "Line integrals and surface integrals", "Green's theorem in the plane"]),
    "probstat": ("Probability and Statistics", 4, [
        "Measures of central tendency and dispersion", "Axioms of probability, conditional probability",
        "Binomial, Poisson and normal distribution", "Correlation and regression",
        "Tests of significance: t test and chi square test"]),
    "ode_own": ("Differential Equations", 4, [
        "First order equations, exact equations", "Linear differential equations with constant coefficients",
        "Wronskian and variation of parameters", "Mathematical modelling with differential equations"]),
}

OWN = ("Riverside College of Science", "R", [
    "calc1", "calc2", "vector", "real1", "linalg", "algebra1", "real2", "ode_own", "algebra2", "complex",
    "probstat", "pde", "mechanics", "numerical", "numerical_lab_c", "c_prog", "stats", "transforms",
    "number", "graph", "metric", "history", "project"])

PEERS = [
    ("Northfield University", "N", [
        "calc1", "multivariable", "real1", "linalg", "python", "real2", "algebra1", "ode", "algebra2",
        "complex", "prob", "numerical", "numerical_lab", "inference", "pde", "lp", "modelling", "data",
        "ml", "graph", "topology", "internship", "project"]),
    ("Eastbrook Institute of Science", "E", [
        "calc1", "multivariable", "vector", "real1", "linalg", "python", "real2", "algebra1", "ode",
        "algebra2", "complex", "prob", "numerical", "numerical_lab", "inference", "pde", "topology",
        "metric", "lp", "sci_comp", "functional", "diffgeo", "project"]),
    ("Lakeshore University", "L", [
        "calc1", "real1", "linalg", "c_prog", "real2", "algebra1", "ode", "algebra2", "complex", "stats",
        "numerical", "numerical_lab_c", "pde", "mechanics", "lp", "or", "transforms", "number", "discrete",
        "diffgeo", "project"]),
    ("Westgate College", "W", [
        "calc1", "multivariable", "real1", "linalg", "python", "algebra1", "ode", "complex", "prob",
        "stats", "numerical", "numerical_lab", "r_stats", "data", "lp", "modelling", "finance", "excel",
        "internship", "project"]),
    ("Hillcrest University", "H", [
        "calc1", "multivariable", "vector", "real1", "linalg", "python", "real2", "algebra1", "ode",
        "algebra2", "complex", "metric", "topology", "prob", "numerical", "numerical_lab", "inference",
        "pde", "timeseries", "ml", "lp", "graph", "crypto", "number", "latex", "project"]),
    ("Southbank Institute of Technology", "S", [
        "calc1", "multivariable", "linalg", "real1", "python", "discrete", "graph", "ode", "prob",
        "numerical", "numerical_lab", "data", "sql", "inference", "ml", "lp", "or", "modelling",
        "sci_comp", "internship", "project"]),
    ("Meadowvale University", "M", [
        "calc1", "real1", "linalg", "real2", "algebra1", "ode", "algebra2", "complex", "prob", "stats",
        "pde", "mechanics", "transforms", "numerical", "numerical_lab_c", "lp", "number", "history",
        "seminar", "project"]),
    ("Kingsport Science College", "K", [
        "calc1", "multivariable", "real1", "linalg", "python", "real2", "algebra1", "ode", "complex",
        "prob", "numerical", "numerical_lab", "inference", "pde", "stochastic", "lp", "modelling",
        "finance", "data", "latex", "internship", "project"]),
]


def build(name: str, prefix: str, keys: list[str]) -> Programme:
    library = {**LIBRARY, **OWN_EXTRA}
    courses = []
    per_sem = max(1, -(-len(keys) // 6))     # spread over six semesters
    roman = ["I", "II", "III", "IV", "V", "VI"]
    for i, key in enumerate(keys):
        title, credits, topics = library[key]
        sem = min(i // per_sem, 5)
        courses.append(Course(
            code=f"{prefix}MA{sem + 1}{i % per_sem + 1:02d}", title=title, credits=credits,
            semester=roman[sem], category="Project" if key in ("project", "internship") else "Core",
            topics=topics))
    return Programme(institution=name, name="B.Sc. Mathematics (Honours)",
                     source="Fictional sample", year="2025-26", courses=courses)


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "samples"
    (out / "peers").mkdir(parents=True, exist_ok=True)
    save_programme(build(*OWN), out / "riverside.json")
    for name, prefix, keys in PEERS:
        slug = name.split()[0].lower()
        save_programme(build(name, prefix, keys), out / "peers" / f"{slug}.json")
    print(f"wrote 1 + {len(PEERS)} programmes to {out}")


if __name__ == "__main__":
    main()
