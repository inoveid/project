import { describe, expect, it } from 'vitest';
import { getStatusConfig, isTaskValid, isTransitionAllowed, getTransitionError } from './statusConfig';

describe('getStatusConfig', () => {
  it('returns config for each status', () => {
    expect(getStatusConfig('backlog').label).toBe('Backlog');
    expect(getStatusConfig('in_progress').colorClasses).toContain('blue');
    expect(getStatusConfig('awaiting_user').label).toContain('Ждёт решения');
    expect(getStatusConfig('done').colorClasses).toContain('green');
    expect(getStatusConfig('error').colorClasses).toContain('red');
  });
});

describe('isTaskValid', () => {
  it('returns true when product_id is set', () => {
    expect(isTaskValid({ product_id: 'p-1' })).toBe(true);
  });

  it('returns false when product_id is null', () => {
    expect(isTaskValid({ product_id: null })).toBe(false);
  });
});

describe('isTransitionAllowed', () => {
  it('allows backlog → in_progress', () => {
    expect(isTransitionAllowed('backlog', 'in_progress')).toBe(true);
  });

  it('allows in_progress → done', () => {
    expect(isTransitionAllowed('in_progress', 'done')).toBe(true);
  });

  it('allows done → in_progress', () => {
    expect(isTransitionAllowed('done', 'in_progress')).toBe(true);
  });

  it('allows error → in_progress', () => {
    expect(isTransitionAllowed('error', 'in_progress')).toBe(true);
  });

  it('disallows backlog → done', () => {
    expect(isTransitionAllowed('backlog', 'done')).toBe(false);
  });

  it('disallows in_progress → backlog', () => {
    expect(isTransitionAllowed('in_progress', 'backlog')).toBe(false);
  });

  it('disallows awaiting_user → done', () => {
    expect(isTransitionAllowed('awaiting_user', 'done')).toBe(false);
  });
});

describe('getTransitionError', () => {
  it('returns null for allowed transitions', () => {
    expect(getTransitionError('backlog', 'in_progress')).toBeNull();
  });

  it('returns error message for disallowed transitions', () => {
    const msg = getTransitionError('backlog', 'done');
    expect(msg).toContain('Backlog');
    expect(msg).toContain('Готово');
  });
});
