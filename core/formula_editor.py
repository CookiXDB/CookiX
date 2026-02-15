"""
Custom Formula Editor for VectorDB
Allows users to define their own distance calculation formulas at runtime
"""

import numpy as np
import re
from typing import Callable, Dict, Any, Optional


class FormulaParser:
    """Parse and evaluate mathematical formulas for distance calculation"""
    
    def __init__(self):
        # Safe mathematical functions available in formulas
        self.safe_functions = {
            # Basic math
            'sqrt': np.sqrt,
            'abs': np.abs,
            'pow': np.power,
            'exp': np.exp,
            'log': np.log,
            'log10': np.log10,
            
            # Trigonometric
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
            'arcsin': np.arcsin,
            'arccos': np.arccos,
            'arctan': np.arctan,
            
            # Aggregation
            'sum': np.sum,
            'mean': np.mean,
            'max': np.max,
            'min': np.min,
            'std': np.std,
            
            # Array operations
            'dot': np.dot,
            'norm': np.linalg.norm,
            
            # Special
            'pi': np.pi,
            'e': np.e,
        }
        
        self.compiled_formulas: Dict[str, Callable] = {}
    
    def validate_formula(self, formula: str) -> tuple[bool, str]:
        """
        Validate a formula string for safety and syntax
        
        Returns:
            (is_valid, error_message)
        """
        # Check for dangerous operations
        dangerous_patterns = [
            r'__',  # Dunder methods
            r'import\s',  # Import statements
            r'eval\s*\(',  # eval calls
            r'exec\s*\(',  # exec calls
            r'open\s*\(',  # file operations
            r'os\.',  # OS operations
            r'sys\.',  # System operations
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, formula):
                return False, f"Forbidden pattern detected: {pattern}"
        
        # Check for required variables
        if 'v1' not in formula or 'v2' not in formula:
            return False, "Formula must use variables 'v1' and 'v2' for the two vectors"
        
        # Try to compile
        try:
            # Create test vectors
            test_v1 = np.array([1, 2, 3])
            test_v2 = np.array([4, 5, 6])
            
            # Try to evaluate
            result = self._evaluate_formula(formula, test_v1, test_v2)
            
            # Check if result is a scalar
            if not isinstance(result, (int, float, np.number)):
                return False, "Formula must return a single number (scalar)"
            
            if np.isnan(result) or np.isinf(result):
                return False, "Formula produces NaN or Infinity"
            
            return True, "Formula is valid!"
            
        except Exception as e:
            return False, f"Formula error: {str(e)}"
    
    def _evaluate_formula(self, formula: str, v1: np.ndarray, v2: np.ndarray) -> float:
        """Evaluate a formula with two vectors"""
        # Create a safe namespace with only allowed functions
        namespace = self.safe_functions.copy()
        namespace['v1'] = v1
        namespace['v2'] = v2
        
        # Evaluate the formula
        result = eval(formula, {"__builtins__": {}}, namespace)
        
        return float(result)
    
    def create_distance_function(self, formula: str, name: str = "custom") -> Optional[Callable]:
        """
        Create a distance function from a formula string
        
        Args:
            formula: Mathematical formula as string
            name: Name for this formula
            
        Returns:
            Distance calculation function or None if invalid
        """
        is_valid, message = self.validate_formula(formula)
        
        if not is_valid:
            print(f"Invalid formula: {message}")
            return None
        
        def distance_function(v1: np.ndarray, v2: np.ndarray) -> float:
            return self._evaluate_formula(formula, v1, v2)
        
        # Store the compiled formula
        self.compiled_formulas[name] = distance_function
        
        return distance_function


class CustomFormulaLibrary:
    """Library of predefined formula templates and examples"""
    
    TEMPLATES = {
        "euclidean": {
            "name": "Euclidean Distance",
            "formula": "sqrt(sum((v1 - v2) ** 2))",
            "description": "Standard L2 distance: √Σ(vi - wi)²",
        },
        "manhattan": {
            "name": "Manhattan Distance",
            "formula": "sum(abs(v1 - v2))",
            "description": "L1 distance: Σ|vi - wi|",
        },
        "cosine": {
            "name": "Cosine Distance",
            "formula": "1 - (dot(v1, v2) / (norm(v1) * norm(v2)))",
            "description": "Angular distance: 1 - (v1·v2)/(|v1||v2|)",
        },
        "chebyshev": {
            "name": "Chebyshev Distance",
            "formula": "max(abs(v1 - v2))",
            "description": "L∞ distance: max|vi - wi|",
        },
        "minkowski_3": {
            "name": "Minkowski Distance (p=3)",
            "formula": "pow(sum(pow(abs(v1 - v2), 3)), 1/3)",
            "description": "Minkowski with p=3: (Σ|vi - wi|³)^(1/3)",
        },
        "canberra": {
            "name": "Canberra Distance",
            "formula": "sum(abs(v1 - v2) / (abs(v1) + abs(v2) + 1e-10))",
            "description": "Weighted Manhattan: Σ|vi - wi|/(|vi| + |wi|)",
        },
        "angular_degrees": {
            "name": "Angular Distance (Degrees)",
            "formula": "arccos(dot(v1, v2) / (norm(v1) * norm(v2))) * 180 / pi",
            "description": "Angle between vectors in degrees",
        },
        "squared_euclidean": {
            "name": "Squared Euclidean",
            "formula": "sum((v1 - v2) ** 2)",
            "description": "Euclidean squared (faster): Σ(vi - wi)²",
        },
        "mean_absolute_error": {
            "name": "Mean Absolute Error",
            "formula": "mean(abs(v1 - v2))",
            "description": "Average absolute difference",
        },
        "root_mean_square": {
            "name": "Root Mean Square Distance",
            "formula": "sqrt(mean((v1 - v2) ** 2))",
            "description": "RMS distance: √(mean((vi - wi)²))",
        },
    }
    
    CREATIVE_EXAMPLES = {
        "harmonic_mean": {
            "name": "Harmonic Mean Distance",
            "formula": "sum(1 / (abs(v1 - v2) + 1))",
            "description": "Uses harmonic mean principle",
        },
        "exponential_weight": {
            "name": "Exponential Weighted",
            "formula": "sum(exp(abs(v1 - v2)) - 1)",
            "description": "Exponentially weights larger differences",
        },
        "log_distance": {
            "name": "Logarithmic Distance",
            "formula": "sum(log(abs(v1 - v2) + 1))",
            "description": "Logarithmic scaling of differences",
        },
        "sine_distance": {
            "name": "Sine Wave Distance",
            "formula": "sum(abs(sin(v1 - v2)))",
            "description": "Periodic distance using sine",
        },
        "hybrid_norm": {
            "name": "Hybrid L1/L2",
            "formula": "0.5 * sqrt(sum((v1 - v2) ** 2)) + 0.5 * sum(abs(v1 - v2))",
            "description": "50% Euclidean + 50% Manhattan",
        },
        "normalized_diff": {
            "name": "Normalized Difference",
            "formula": "sum(abs(v1 - v2) / (abs(v1) + abs(v2) + 1)) / len(v1)",
            "description": "Normalized by vector magnitude and dimension",
        },
    }
    
    @classmethod
    def get_template(cls, name: str) -> Optional[Dict[str, str]]:
        """Get a formula template by name"""
        return cls.TEMPLATES.get(name) or cls.CREATIVE_EXAMPLES.get(name)
    
    @classmethod
    def list_all(cls) -> Dict[str, Dict[str, str]]:
        """Get all available templates"""
        return {**cls.TEMPLATES, **cls.CREATIVE_EXAMPLES}
    
    @classmethod
    def get_help_text(cls) -> str:
        """Get help text for formula syntax"""
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                    CUSTOM FORMULA SYNTAX GUIDE                       ║
╚══════════════════════════════════════════════════════════════════════╝

VARIABLES:
  v1, v2     - The two vectors being compared

BASIC OPERATIONS:
  +, -, *, /  - Arithmetic operations
  **          - Power (e.g., v1 ** 2 for squaring)
  ()          - Grouping/parentheses

MATHEMATICAL FUNCTIONS:
  sqrt(x)     - Square root
  abs(x)      - Absolute value
  pow(x, y)   - x raised to power y
  exp(x)      - e^x
  log(x)      - Natural logarithm
  log10(x)    - Base-10 logarithm

TRIGONOMETRIC:
  sin(x), cos(x), tan(x)       - Basic trig functions
  arcsin(x), arccos(x), arctan(x) - Inverse trig

ARRAY OPERATIONS:
  sum(x)      - Sum all elements
  mean(x)     - Average of elements
  max(x)      - Maximum element
  min(x)      - Minimum element
  std(x)      - Standard deviation
  dot(v1,v2)  - Dot product
  norm(x)     - Vector magnitude/length

CONSTANTS:
  pi          - π (3.14159...)
  e           - Euler's number (2.71828...)

EXAMPLES:
  1. Euclidean:    sqrt(sum((v1 - v2) ** 2))
  2. Manhattan:    sum(abs(v1 - v2))
  3. Cosine:       1 - (dot(v1, v2) / (norm(v1) * norm(v2)))
  4. Custom:       sqrt(sum((v1 - v2) ** 2)) + 0.1 * sum(abs(v1 - v2))
  5. Weighted:     sqrt(sum([1,2,3] * (v1 - v2) ** 2))  # dimension weights

TIPS:
  • Formula must use both v1 and v2
  • Formula must return a single number
  • Use parentheses to control order of operations
  • Test with simple vectors first
  • Avoid division by zero (add small epsilon: + 1e-10)

╚══════════════════════════════════════════════════════════════════════╝
        """


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("  Custom Formula Editor - Test Suite")
    print("=" * 70)
    
    parser = FormulaParser()
    library = CustomFormulaLibrary()
    
    # Test some formulas
    test_vectors = [
        (np.array([1, 2, 3]), np.array([4, 5, 6])),
        (np.array([0, 0, 0]), np.array([1, 1, 1])),
        (np.array([1, 0, 0]), np.array([0, 1, 0])),
    ]
    
    print("\nTesting predefined formulas:\n")
    
    for template_name, template_info in library.TEMPLATES.items():
        formula = template_info['formula']
        print(f"{template_info['name']}:")
        print(f"  Formula: {formula}")
        
        is_valid, message = parser.validate_formula(formula)
        if is_valid:
            func = parser.create_distance_function(formula, template_name)
            print(f"  Status: ✓ Valid")
            print(f"  Test results:")
            for v1, v2 in test_vectors:
                result = func(v1, v2)
                print(f"    {v1} <-> {v2}: {result:.4f}")
        else:
            print(f"  Status: ✗ {message}")
        print()
    
    print("\n" + "=" * 70)
    print("  Custom Formula Examples")
    print("=" * 70)
    
    custom_formulas = [
        ("My Hybrid", "0.7 * sqrt(sum((v1 - v2) ** 2)) + 0.3 * max(abs(v1 - v2))"),
        ("Exponential", "sum(exp(abs(v1 - v2) / 10))"),
        ("Logarithmic", "sum(log(abs(v1 - v2) + 1))"),
    ]
    
    print()
    for name, formula in custom_formulas:
        print(f"{name}:")
        print(f"  Formula: {formula}")
        is_valid, message = parser.validate_formula(formula)
        if is_valid:
            func = parser.create_distance_function(formula, name)
            v1, v2 = test_vectors[0]
            result = func(v1, v2)
            print(f"  Result: {result:.4f} ✓")
        else:
            print(f"  Error: {message} ✗")
        print()
