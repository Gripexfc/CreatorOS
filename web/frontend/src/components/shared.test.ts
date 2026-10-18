import { describe, expect, it } from 'vitest';
import { connectorStateName } from './shared';

describe('connector status copy', () => {
  it('keeps mock connections distinct from real login', () => {
    expect(connectorStateName('connected', 'mock')).toBe('本地演示已连接');
    expect(connectorStateName('connected', 'browser')).toBe('已登录，等待读取账号');
  });
});
