-- Distinguish meal feedback from likes/dislikes stated via update_profile (incl. onboarding).
-- Both feed the preference model; only 'profile' rows count toward onboarding's 3 loves / 3 dislikes.
alter table public.feedback_events
  add column source text not null default 'feedback'
  check (source in ('feedback', 'profile'));
