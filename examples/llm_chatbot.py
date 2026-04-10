"""
ValidEDI Interactive LLM Chatbot
=================================

An interactive command-line chatbot for exploring EDI files using LLM-powered Q&A.

Usage:
    python llm_chatbot.py path/to/file.edi

Requirements:
    - An LLM provider (OpenAI, Groq, etc.)
    - API key configured in environment or code
"""

import sys
from validedi import parse, validate
from validedi.llm import LLMExplainer


def create_llm():
    """
    Create and return an LLM callable.
    
    Modify this function to use your preferred LLM provider.
    """
    try:
        from groq import Groq
        import os
        from pathlib import Path

        # Load .env file if present
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('GROQ_API_KEY='):
                    os.environ['GROQ_API_KEY'] = line.split('=', 1)[1].strip()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("⚠️  GROQ_API_KEY not set. Add it to a .env file or set it as an environment variable.")
            return None
        
        client = Groq(api_key=api_key)
        
        def llm(prompt: str) -> str:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            return response.choices[0].message.content
        
        print("✅ Using Groq Llama 3.1")
        return llm
        
    except ImportError:
        print("❌ Groq package not installed. Install with: pip install groq")
        return None
    except Exception as e:
        print(f"❌ Error initializing Groq: {e}")
        return None


def print_banner():
    """Print welcome banner."""
    print("=" * 70)
    print("  ValidEDI Interactive LLM Chatbot")
    print("=" * 70)
    print()
    print("Ask questions about your EDI file in plain English!")
    print()
    print("Commands:")
    print("  - Type your question and press Enter")
    print("  - 'report' - Show full explanation report")
    print("  - 'summary' - Show validation summary")
    print("  - 'help' - Show this help message")
    print("  - 'quit' or 'exit' - Exit the chatbot")
    print("=" * 70)
    print()


def print_help():
    """Print help message."""
    print("\n" + "=" * 70)
    print("  Help")
    print("=" * 70)
    print("\nExample questions you can ask:")
    print("  • What is the total billed amount?")
    print("  • How many claims are in this file?")
    print("  • What errors need to be fixed?")
    print("  • Who is the billing provider?")
    print("  • What is the payment method?")
    print("  • Are there any critical errors?")
    print("  • What should I do next?")
    print("  • Explain the validation errors in simple terms")
    print("\nCommands:")
    print("  • report - Show full explanation report")
    print("  • summary - Show validation summary")
    print("  • help - Show this help message")
    print("  • quit/exit - Exit the chatbot")
    print("=" * 70 + "\n")


def run_chatbot(filepath: str):
    """
    Run the interactive chatbot.
    
    Args:
        filepath: Path to EDI file
    """
    print_banner()
    
    # Create LLM
    llm = create_llm()
    if llm is None:
        print("\n❌ No LLM available. Chatbot requires an LLM provider.")
        print("💡 Configure your LLM in the create_llm() function.")
        return
    
    # Parse and validate EDI file
    print(f"📄 Loading EDI file: {filepath}")
    try:
        edi_result = parse(filepath)
        val_result = validate(edi_result)
        print(f"✅ File loaded: {edi_result.envelope.transaction_type}")
        print(f"📊 Validation: {'Valid' if val_result.is_valid else 'Invalid'} ({val_result.error_count} errors, {val_result.warning_count} warnings)")
        print()
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Create explainer
    explainer = LLMExplainer(llm=llm)
    
    # Generate initial report
    print("🤖 Generating explanation report...")
    try:
        report_result = explainer.explain(edi_result, val_result)
        print("✅ Report ready!\n")
    except Exception as e:
        print(f"❌ Error generating report: {e}\n")
        report_result = None
    
    # Chat loop
    print("💬 Ready for questions! Type 'help' for examples.\n")
    
    while True:
        try:
            # Get user input
            question = input("You: ").strip()
            
            if not question:
                continue
            
            # Handle commands
            if question.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            elif question.lower() == 'help':
                print_help()
                continue
            
            elif question.lower() == 'report':
                if report_result:
                    print("\n" + "=" * 70)
                    print("  Full Explanation Report")
                    print("=" * 70)
                    print(report_result.report)
                    print("=" * 70 + "\n")
                else:
                    print("\n❌ Report not available.\n")
                continue
            
            elif question.lower() == 'summary':
                print("\n" + "=" * 70)
                print("  Validation Summary")
                print("=" * 70)
                print(f"Transaction: {edi_result.envelope.transaction_type}")
                print(f"Status: {'Valid' if val_result.is_valid else 'Invalid'}")
                print(f"Errors: {val_result.error_count}")
                print(f"Warnings: {val_result.warning_count}")
                if val_result.errors:
                    print("\nIssues:")
                    for issue in val_result.errors[:5]:
                        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
                        print(f"  {icon} [{issue.code}] {issue.message}")
                    if len(val_result.errors) > 5:
                        print(f"  ... and {len(val_result.errors) - 5} more")

                print("=" * 70 + "\n")
                continue
            
            # Ask LLM
            print("🤖 Thinking...")
            try:
                answer = explainer.ask_followup(question, edi_result, val_result)
                print(f"\nBot: {answer}\n")
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python llm_chatbot.py <path-to-edi-file>")
        print("\nExample:")
        print("  python llm_chatbot.py samples/837P/claim1.edi")
        sys.exit(1)
    
    filepath = sys.argv[1]
    run_chatbot(filepath)


if __name__ == "__main__":
    main()
