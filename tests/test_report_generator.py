from src.services.report_generator import ReportGenerator


def test_generate_email_html_handles_dict_summary_and_non_dict_crm_updates():
    generator = ReportGenerator()

    context = {
        "subject": "Avon Sunday Meeting",
        "summary": {"key_agreements": ["Discount approved"], "next": "Send quote"},
        "sentiment": "positive",
        "sentiment_timeline": ["Kickoff positive", "Pricing concern", "Aligned on next steps"],
        "churn_risk": {"level": "medium", "reason": "Budget pressure"},
        "customer_satisfaction": {"score": "8/10", "reason": "Good product fit"},
        "expansion_likelihood": {
            "level": "high",
            "score": "82",
            "reason": "Customer asked about analytics add-on",
            "products": ["Analytics Pro", "Support Plus"],
        },
        "tasks": ["Send quote", {"owner": "Graham", "task": "Follow up"}],
        "crm_updates": "Opportunity stage moved to Proposal",
        "crm_link": "https://dynamics.microsoft.com",
    }

    html = generator.generate_email_html(context)

    assert "Avon Sunday Meeting" in html
    assert "Discount approved" in html
    assert '"key_agreements"' not in html
    assert "Opportunity stage moved to Proposal" in html
    assert "AI Sentiment Analysis" in html
    assert "Expansion Opportunity" in html
    assert "Likelihood to Purchase Additional Products" in html
    assert "Analytics Pro, Support Plus" in html
