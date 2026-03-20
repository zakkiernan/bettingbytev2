from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.services import audit_service
from database.db import Base
from database.models import SignalAuditTrail


class AuditServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(
            self.engine,
            tables=[SignalAuditTrail.__table__],
        )

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[SignalAuditTrail.__table__],
        )
        self.engine.dispose()

    @contextmanager
    def session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def test_audit_queries_return_sorted_rows(self):
        with self.session_scope() as session:
            session.add_all(
                [
                    SignalAuditTrail(
                        game_id="G1",
                        player_id="P1",
                        stat_type="points",
                        snapshot_phase="early",
                        line=24.5,
                        projected_value=25.8,
                        edge=1.3,
                        confidence=0.62,
                        recommended_side="OVER",
                        readiness_status="ready",
                        blockers_json=None,
                        warnings_json='["Signal is leaning on official injury team context"]',
                        breakdown_json='{"base_scoring": 25.8, "projected_points": 25.8}',
                        captured_at=datetime(2026, 3, 16, 16, 0, 0),
                    ),
                    SignalAuditTrail(
                        game_id="G1",
                        player_id="P1",
                        stat_type="points",
                        snapshot_phase="tip",
                        line=25.5,
                        projected_value=24.8,
                        edge=-0.7,
                        confidence=0.58,
                        recommended_side=None,
                        readiness_status="blocked",
                        blockers_json='["Opportunity confidence is only 0.30"]',
                        warnings_json=None,
                        breakdown_json='{"base_scoring": 24.8, "projected_points": 24.8}',
                        captured_at=datetime(2026, 3, 16, 19, 0, 0),
                    ),
                ]
            )

        with self.session_scope() as session:
            player_rows = audit_service.get_player_game_audit_rows(session, player_id="P1", game_id="G1")
            game_rows = audit_service.get_game_audit_rows(session, game_id="G1")
            recent_rows = audit_service.get_recent_audit_rows(session, limit=1)

        self.assertEqual([row.snapshot_phase for row in player_rows], ["early", "tip"])
        self.assertEqual(game_rows[1].blockers, ["Opportunity confidence is only 0.30"])
        self.assertEqual(game_rows[0].warnings, ["Signal is leaning on official injury team context"])
        self.assertEqual(recent_rows[0].snapshot_phase, "tip")


if __name__ == "__main__":
    unittest.main()
