"""
Session review tools for D&D AI Dungeon Master.
Provides tools to review previous session plans and outcomes.
"""
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


SESSIONS_BASE_PATH = "mirror/sessions"


class SessionReview(BaseModel):
    """
    Tool for reviewing the most recent session in a campaign.
    Distinguishes between INTENDED (planning notes) and ACTUAL (what happened).
    """
    campaign_id: str
    
    def get_most_recent_session(self) -> Optional[dict]:
        """
        Get the most recent completed or open session for this campaign.
        Returns None if no sessions exist.
        """
        session_dir = Path(SESSIONS_BASE_PATH) / self.campaign_id
        
        if not session_dir.exists():
            return None
        
        sessions = []
        for session_file in session_dir.glob("*_session.json"):
            try:
                session_data = json.loads(session_file.read_text(encoding="utf-8"))
                sessions.append(session_data)
            except (json.JSONDecodeError, IOError):
                continue
        
        if not sessions:
            return None
        
        # Sort by creation date, newest first
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions[0]
    
    def format_review(self, session: dict) -> str:
        """
        Format session data to clearly distinguish INTENDED vs ACTUAL.
        
        Returns a structured text summary that the AI can use to understand:
        - What was originally planned (INTENDED)
        - What actually happened during gameplay (ACTUAL)
        """
        session_id = session.get("session_id", "unknown")
        session_number = session.get("session_number", "unknown")
        status = session.get("status", "unknown")
        created_at = session.get("created_at", "unknown")
        
        # Extract INTENDED information from session_plan
        session_plan = session.get("session_plan", {})
        planning_notes = session_plan.get("planning_notes", {})
        narrative_overview = session_plan.get("narrative_overview", "No overview available")
        beats = session_plan.get("beats", [])
        
        # Extract ACTUAL information
        chat_history = session.get("chat_history", [])
        turn_count = session.get("turn_count", 0)
        summary = session.get("summary", "No summary available")
        post_session_analysis = session.get("post_session_analysis", None)
        
        # Build formatted review
        review = f"""=== SESSION REVIEW: Session {session_number} (ID: {session_id}) ===
Status: {status}
Created: {created_at}
Turns Played: {turn_count}

---
SECTION 1: INTENDED SESSION PLAN
---
This section describes what was ORIGINALLY PLANNED for this session before it was played.

Analysis of Campaign (at planning time):
{planning_notes.get('analysis_of_campaign_so_far', 'Not available')}

Narrative Overview (intended):
{narrative_overview}

Intended Beats:
"""
        
        for i, beat in enumerate(beats, 1):
            title = beat.get("title", f"Beat {i}")
            description = beat.get("description", "No description")
            review += f"\n  Beat {i}: {title}\n"
            review += f"    {description}\n"
        
        review += "\n---\nSECTION 2: ACTUAL SESSION OUTCOME\n---\n"
        review += "This section describes what ACTUALLY HAPPENED when the session was played.\n\n"
        
        if post_session_analysis:
            review += f"Post-Session Analysis:\n{post_session_analysis}\n\n"
        else:
            review += "Post-Session Analysis: Not yet available (session may still be in progress or analysis not generated)\n\n"
        
        review += f"Session Summary (from gameplay):\n{summary}\n\n"
        
        # if chat_history:
        #     review += f"Turn History ({len(chat_history)} turns):\n"
        #     for turn in chat_history[:5]:  # Show first 5 turns
        #         turn_num = turn.get("turn_number", "?")
        #         user_input = turn.get("user_input", "")
        #         turn_summary = turn.get("turn_summary", "")
        #         review += f"  Turn {turn_num}: {user_input}\n"
        #         if turn_summary:
        #             review += f"    Summary: {turn_summary}\n"
        #     if len(chat_history) > 5:
        #         review += f"  ... (and {len(chat_history) - 5} more turns)\n"
        # else:
        #     review += "Turn History: No turns played yet\n"
        
        review += "\n=== END SESSION REVIEW ===\n"
        
        return review
    
    def execute(self) -> str:
        """
        Execute the session review tool.
        Returns formatted review or message if no sessions exist.
        """
        session = self.get_most_recent_session()
        
        if not session:
            return f"No previous sessions found for campaign {self.campaign_id}. This must be the first session."
        
        return self.format_review(session)
    
    @classmethod
    def from_campaign(cls, campaign_id: str) -> "SessionReview":
        """Create a SessionReview for a specific campaign."""
        return cls(campaign_id=campaign_id)
    
    def as_function(self):
        """
        Return this as a callable function for the Agents SDK.
        This allows it to be used as a tool by wrapping it in an Agent.
        """
        def review_last_session() -> str:
            """
            Review the most recent session from this campaign.
            
            Returns a structured summary that clearly distinguishes:
            - INTENDED: What was originally planned for the session (planning notes, narrative overview, intended beats)
            - ACTUAL: What actually happened during gameplay (post-session analysis, turn summaries, player actions)
            
            Use this tool at the start of session planning to understand where the campaign currently stands.
            """
            return self.execute()
        
        return review_last_session
