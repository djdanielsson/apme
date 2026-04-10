import { type RefObject, useRef, useState, useEffect } from 'react';
import {
  Button,
  Label,
  TextInput,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  ToolbarGroup,
} from '@patternfly/react-core';
import { FilterIcon, SearchIcon, TimesIcon } from '@patternfly/react-icons';
import { SEV_CSS_VAR, SEVERITY_ORDER, SEVERITY_LABELS, SCOPE_ORDER, SCOPE_LABELS, FIX_ORDER, FIX_LABELS, bareRuleId } from './severity';

interface ViolationOutputToolbarProps {
  searchText: string;
  onSearchChange: (text: string) => void;
  sevFilters: Set<string>;
  ruleFilters: Set<string>;
  scopeFilters: Set<number>;
  fixFilters: Set<number>;
  sevCounts: Map<string, number>;
  scopeCounts: Map<number, number>;
  fixCounts: Map<number, number>;
  uniqueRules: string[];
  onSevChange: (next: Set<string>) => void;
  onRuleChange: (next: Set<string>) => void;
  onScopeChange: (next: Set<number>) => void;
  onFixChange: (next: Set<number>) => void;
  isRemediate?: boolean;
  filteredCount: number;
  totalCount: number;
}

export function ViolationOutputToolbar({
  searchText,
  onSearchChange,
  sevFilters,
  ruleFilters,
  scopeFilters,
  fixFilters,
  sevCounts,
  scopeCounts,
  fixCounts,
  uniqueRules,
  onSevChange,
  onRuleChange,
  onScopeChange,
  onFixChange,
  isRemediate = false,
  filteredCount,
  totalCount,
}: ViolationOutputToolbarProps) {
  const [filterMenuOpen, setFilterMenuOpen] = useState<'severity' | 'scope' | 'fix' | 'rule' | null>(null);
  const sevRef = useRef<HTMLDivElement>(null);
  const scopeRef = useRef<HTMLDivElement>(null);
  const fixRef = useRef<HTMLDivElement>(null);
  const ruleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!filterMenuOpen) return;
    const handler = (e: MouseEvent) => {
      const refs: Record<string, RefObject<HTMLDivElement | null>> = { severity: sevRef, scope: scopeRef, fix: fixRef, rule: ruleRef };
      const ref = refs[filterMenuOpen];
      if (ref?.current && !ref.current.contains(e.target as Node)) {
        setFilterMenuOpen(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [filterMenuOpen]);

  const fixLabelFor = (rc: number) => (rc === 1 && isRemediate) ? 'Fixed' : (FIX_LABELS[rc] || `Fix ${rc}`);

  const hasFilters = sevFilters.size > 0 || ruleFilters.size > 0 || scopeFilters.size > 0 || fixFilters.size > 0 || searchText.length > 0;
  const clearAll = () => {
    onSevChange(new Set());
    onRuleChange(new Set());
    onScopeChange(new Set());
    onFixChange(new Set());
    onSearchChange('');
  };

  const toggleSev = (cls: string) => {
    const next = new Set(sevFilters);
    if (next.has(cls)) next.delete(cls); else next.add(cls);
    onSevChange(next);
  };

  const toggleRule = (rule: string) => {
    const next = new Set(ruleFilters);
    if (next.has(rule)) next.delete(rule); else next.add(rule);
    onRuleChange(next);
  };

  const toggleScope = (scope: number) => {
    const next = new Set(scopeFilters);
    if (next.has(scope)) next.delete(scope); else next.add(scope);
    onScopeChange(next);
  };

  const toggleFix = (rc: number) => {
    const next = new Set(fixFilters);
    if (next.has(rc)) next.delete(rc); else next.add(rc);
    onFixChange(next);
  };

  return (
    <Toolbar className="apme-output-toolbar">
      <ToolbarContent>
        <ToolbarItem>
          <div className="apme-toolbar-search">
            <SearchIcon className="apme-toolbar-search-icon" />
            <TextInput
              aria-label="Search violations"
              placeholder="Search..."
              value={searchText}
              onChange={(_e, val) => onSearchChange(val)}
              className="apme-toolbar-search-input"
            />
            {searchText && (
              <Button variant="plain" onClick={() => onSearchChange('')} aria-label="Clear search" size="sm">
                <TimesIcon />
              </Button>
            )}
          </div>
        </ToolbarItem>

        <ToolbarGroup>
          {/* Severity filter */}
          <ToolbarItem>
            <div className="apme-filter-anchor" ref={sevRef}>
              <Button
                variant="secondary"
                onClick={() => setFilterMenuOpen(filterMenuOpen === 'severity' ? null : 'severity')}
                size="sm"
                icon={<FilterIcon />}
              >
                Severity{sevFilters.size > 0 ? ` (${sevFilters.size})` : ''}
              </Button>
              {filterMenuOpen === 'severity' && (
                <div className="apme-filter-popover" onClick={(e) => e.stopPropagation()}>
                  <div className="apme-filter-scroll">
                    {SEVERITY_ORDER.map((cls) => {
                      const count = sevCounts.get(cls) ?? 0;
                      if (count === 0) return null;
                      return (
                        <label key={cls} className="apme-filter-option">
                          <input type="checkbox" checked={sevFilters.has(cls)} onChange={() => toggleSev(cls)} />
                          <span className="apme-sev-dot" style={{ background: SEV_CSS_VAR[cls] }} />
                          <span style={{ flex: 1 }}>{SEVERITY_LABELS[cls]}</span>
                          <span style={{ opacity: 0.6, fontSize: 12 }}>{count}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </ToolbarItem>

          {/* Scope filter */}
          <ToolbarItem>
            <div className="apme-filter-anchor" ref={scopeRef}>
              <Button
                variant="secondary"
                onClick={() => setFilterMenuOpen(filterMenuOpen === 'scope' ? null : 'scope')}
                size="sm"
                icon={<FilterIcon />}
              >
                Scope{scopeFilters.size > 0 ? ` (${scopeFilters.size})` : ''}
              </Button>
              {filterMenuOpen === 'scope' && (
                <div className="apme-filter-popover" onClick={(e) => e.stopPropagation()}>
                  <div className="apme-filter-scroll">
                    {SCOPE_ORDER.map((s) => {
                      const count = scopeCounts.get(s) ?? 0;
                      if (count === 0) return null;
                      return (
                        <label key={s} className="apme-filter-option">
                          <input type="checkbox" checked={scopeFilters.has(s)} onChange={() => toggleScope(s)} />
                          <span style={{ flex: 1 }}>{SCOPE_LABELS[s]}</span>
                          <span style={{ opacity: 0.6, fontSize: 12 }}>{count}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </ToolbarItem>

          {/* Fix type filter */}
          <ToolbarItem>
            <div className="apme-filter-anchor" ref={fixRef}>
              <Button
                variant="secondary"
                onClick={() => setFilterMenuOpen(filterMenuOpen === 'fix' ? null : 'fix')}
                size="sm"
                icon={<FilterIcon />}
              >
                Fix{fixFilters.size > 0 ? ` (${fixFilters.size})` : ''}
              </Button>
              {filterMenuOpen === 'fix' && (
                <div className="apme-filter-popover" onClick={(e) => e.stopPropagation()}>
                  <div className="apme-filter-scroll">
                    {FIX_ORDER.map((rc) => {
                      const count = fixCounts.get(rc) ?? 0;
                      if (count === 0) return null;
                      return (
                        <label key={rc} className="apme-filter-option">
                          <input type="checkbox" checked={fixFilters.has(rc)} onChange={() => toggleFix(rc)} />
                          <span style={{ flex: 1 }}>{fixLabelFor(rc)}</span>
                          <span style={{ opacity: 0.6, fontSize: 12 }}>{count}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </ToolbarItem>

          {/* Rule filter */}
          <ToolbarItem>
            <div className="apme-filter-anchor" ref={ruleRef}>
              <Button
                variant="secondary"
                onClick={() => setFilterMenuOpen(filterMenuOpen === 'rule' ? null : 'rule')}
                size="sm"
                icon={<FilterIcon />}
              >
                Rule{ruleFilters.size > 0 ? ` (${ruleFilters.size})` : ''}
              </Button>
              {filterMenuOpen === 'rule' && uniqueRules.length > 0 && (
                <div className="apme-filter-popover" onClick={(e) => e.stopPropagation()}>
                  <div className="apme-filter-scroll">
                    {uniqueRules.map((r) => (
                      <label key={r} className="apme-filter-option">
                        <input type="checkbox" checked={ruleFilters.has(r)} onChange={() => toggleRule(r)} />
                        <span style={{ fontFamily: 'var(--pf-t--global--font--family--mono)', fontSize: 12 }}>{bareRuleId(r)}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ToolbarItem>
        </ToolbarGroup>

        {hasFilters && (
          <ToolbarGroup>
            <ToolbarItem>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {Array.from(sevFilters).map(cls => (
                  <Label key={cls} onClose={() => toggleSev(cls)} isCompact>
                    {SEVERITY_LABELS[cls] || cls}
                  </Label>
                ))}
                {Array.from(scopeFilters).map(s => (
                  <Label key={s} onClose={() => toggleScope(s)} isCompact variant="outline">
                    {SCOPE_LABELS[s] || `Scope ${s}`}
                  </Label>
                ))}
                {Array.from(fixFilters).map(rc => (
                  <Label key={rc} onClose={() => toggleFix(rc)} isCompact variant="outline">
                    {fixLabelFor(rc)}
                  </Label>
                ))}
                {Array.from(ruleFilters).map(r => (
                  <Label key={r} onClose={() => toggleRule(r)} isCompact variant="outline">
                    {bareRuleId(r)}
                  </Label>
                ))}
                {searchText && (
                  <Label onClose={() => onSearchChange('')} isCompact variant="outline">
                    Search: {searchText}
                  </Label>
                )}
                <Button variant="link" onClick={clearAll} size="sm">Clear all</Button>
              </div>
            </ToolbarItem>
          </ToolbarGroup>
        )}

        <ToolbarItem style={{ marginLeft: 'auto' }}>
          {hasFilters && (
            <span style={{ fontSize: 13, opacity: 0.7 }}>
              {filteredCount} of {totalCount}
            </span>
          )}
        </ToolbarItem>
      </ToolbarContent>
    </Toolbar>
  );
}
