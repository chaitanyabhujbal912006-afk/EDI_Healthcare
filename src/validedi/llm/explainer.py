"""
LLM-powered EDI explanation engine.

Supports any LLM provider through a simple callable interface.
Falls back to rule-based templates when no LLM is provided.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Any

from .prompts import build_explanation_prompt, build_qa_prompt
from .templates import render_rule_based_report


# Type alias for LLM callable
LLMCallable = Callable[[str], str]


@dataclass
class ExplainResult:
    """
    Result of an EDI explanation.
    
    Attributes:
        report: The generated explanation text
        source: Source of the explanation ("llm" or "rule_based")
        metadata: Additional metadata (model info, tokens, etc.)
    """
    report: str
    source: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def __str__(self) -> str:
        return self.report


class LLMExplainer:
    """
    LLM-powered EDI explanation engine.
    
    Accepts any LLM callable that takes a prompt string and returns a response string.
    Falls back to rule-based templates when no LLM is provided.
    
    Example:
        # With OpenAI
        from openai import OpenAI
        client = OpenAI(api_key="...")
        llm = lambda prompt: client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
        
        explainer = LLMExplainer(llm=llm)
        result = explainer.explain(edi_result, val_result)
        print(result.report)
        
        # With Groq
        from groq import Groq
        client = Groq(api_key="...")
        llm = lambda prompt: client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
        
        explainer = LLMExplainer(llm=llm)
        
        # Without LLM (rule-based)
        explainer = LLMExplainer()  # Falls back to templates
    """
    
    def __init__(self, llm: Optional[LLMCallable] = None):
        """
        Initialize the explainer.
        
        Args:
            llm: Optional callable that takes a prompt string and returns a response string.
                 If None, uses rule-based templates.
        """
        self.llm = llm
    
    def explain(
        self,
        edi_result: Any,
        val_result: Any,
        extracted_data: Optional[Any] = None,
        force_rule_based: bool = False
    ) -> ExplainResult:
        """
        Generate a plain-English explanation of the EDI file.
        
        Args:
            edi_result: Parsed EDI result from parser.parse()
            val_result: Validation result from validator.validate()
            extracted_data: Optional extracted business data (from extract_claims, extract_payments, extract_enrollments)
            force_rule_based: If True, skip LLM and use rule-based templates
            
        Returns:
            ExplainResult with the generated report
        """
        # Use rule-based if forced or no LLM provided
        if force_rule_based or self.llm is None:
            report = render_rule_based_report(edi_result, val_result)
            return ExplainResult(
                report=report,
                source="rule_based",
                metadata={"method": "template"}
            )
        
        # Try LLM
        try:
            prompt = build_explanation_prompt(edi_result, val_result, extracted_data)
            response = self.llm(prompt)
            
            if response and response.strip():
                return ExplainResult(
                    report=response.strip(),
                    source="llm",
                    metadata={"method": "llm_provided"}
                )
        except Exception as e:
            # LLM failed, fall back to rule-based
            report = render_rule_based_report(edi_result, val_result)
            return ExplainResult(
                report=report,
                source="rule_based",
                metadata={"method": "fallback", "error": str(e)}
            )
        
        # Fallback if LLM returned empty
        report = render_rule_based_report(edi_result, val_result)
        return ExplainResult(
            report=report,
            source="rule_based",
            metadata={"method": "fallback", "reason": "empty_response"}
        )
    
    def ask_followup(
        self,
        question: str,
        edi_result: Any,
        val_result: Any,
        extracted_data: Optional[Any] = None
    ) -> str:
        """
        Answer a follow-up question about the EDI file.
        
        Args:
            question: User's question
            edi_result: Parsed EDI result
            val_result: Validation result
            extracted_data: Optional extracted business data
            
        Returns:
            Answer string
        """
        if self.llm is None:
            return (
                "❌ No LLM provided. Q&A requires an LLM instance.\n\n"
                "💡 Pass an LLM callable to LLMExplainer:\n"
                "   explainer = LLMExplainer(llm=your_llm_function)"
            )
        
        try:
            prompt = build_qa_prompt(question, edi_result, val_result, extracted_data)
            response = self.llm(prompt)
            return response.strip() if response else "No response from LLM."
        except Exception as e:
            return f"❌ Error calling LLM: {str(e)}"


# ── Convenience functions ────────────────────────────────────────────────────

def explain(
    edi_result: Any,
    val_result: Any,
    llm: Optional[LLMCallable] = None,
    extracted_data: Optional[Any] = None,
    force_rule_based: bool = False
) -> ExplainResult:
    """
    Generate a plain-English explanation of the EDI file.
    
    Convenience function that creates an LLMExplainer and calls explain().
    
    Args:
        edi_result: Parsed EDI result from parser.parse()
        val_result: Validation result from validator.validate()
        llm: Optional callable that takes a prompt string and returns a response string
        extracted_data: Optional extracted business data (from extract_claims, extract_payments, extract_enrollments)
        force_rule_based: If True, skip LLM and use rule-based templates
        
    Returns:
        ExplainResult with the generated report
        
    Example:
        from validedi import parse, validate, extract_claims
        from validedi.llm import explain
        
        # Parse and extract
        parsed = parse("file.edi")
        validated = validate(parsed)
        claims = extract_claims(parsed)
        
        # Explain with extracted data
        result = explain(parsed, validated, llm=llm, extracted_data=claims)
        print(result.report)
    """
    explainer = LLMExplainer(llm=llm)
    return explainer.explain(edi_result, val_result, extracted_data, force_rule_based)


def ask_followup(
    question: str,
    edi_result: Any,
    val_result: Any,
    llm: Optional[LLMCallable] = None,
    extracted_data: Optional[Any] = None
) -> str:
    """
    Answer a follow-up question about the EDI file.
    
    Convenience function that creates an LLMExplainer and calls ask_followup().
    
    Args:
        question: User's question
        edi_result: Parsed EDI result
        val_result: Validation result
        llm: Optional callable that takes a prompt string and returns a response string
        extracted_data: Optional extracted business data
        
    Returns:
        Answer string
        
    Example:
        from validedi import parse, validate, extract_claims
        from validedi.llm import ask_followup
        
        parsed = parse("file.edi")
        validated = validate(parsed)
        claims = extract_claims(parsed)
        
        answer = ask_followup(
            "What is the total billed amount?",
            parsed,
            validated,
            llm=llm,
            extracted_data=claims
        )
        print(answer)
    """
    explainer = LLMExplainer(llm=llm)
    return explainer.ask_followup(question, edi_result, val_result, extracted_data)
