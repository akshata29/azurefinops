import type { BreakdownNode, ResourceCost } from '../api/types';

export interface ResourceFilters {
  service_category: string;
  service: string;
  resource_type: string;
  resource: string;
}

export const EMPTY_FILTERS: ResourceFilters = {
  service_category: '',
  service: '',
  resource_type: '',
  resource: '',
};

const round2 = (n: number) => Math.round(n * 100) / 100;
const round1 = (n: number) => Math.round(n * 10) / 10;

/** Apply the (AND-combined) cascading filters to a flat resource list. */
export function applyFilters(resources: ResourceCost[], f: ResourceFilters): ResourceCost[] {
  return resources.filter(
    (r) =>
      (!f.service_category || r.service_category === f.service_category) &&
      (!f.service || r.service_name === f.service) &&
      (!f.resource_type || r.resource_type === f.resource_type) &&
      (!f.resource || r.resource_name === f.resource),
  );
}

/** Distinct, sorted cascading options given the current selections above each level. */
export function filterOptions(resources: ResourceCost[], f: ResourceFilters) {
  const distinct = (vals: string[]) => Array.from(new Set(vals.filter(Boolean))).sort();
  const inCat = (r: ResourceCost) => !f.service_category || r.service_category === f.service_category;
  const inSvc = (r: ResourceCost) => inCat(r) && (!f.service || r.service_name === f.service);
  const inType = (r: ResourceCost) => inSvc(r) && (!f.resource_type || r.resource_type === f.resource_type);
  return {
    categories: distinct(resources.map((r) => r.service_category)),
    services: distinct(resources.filter(inCat).map((r) => r.service_name)),
    resource_types: distinct(resources.filter(inSvc).map((r) => r.resource_type)),
    resources: distinct(resources.filter(inType).map((r) => r.resource_name)),
  };
}

/** Build the 4-level ServiceCategory → Service → ResourceType → Resource tree. */
export function buildBreakdown(resources: ResourceCost[]): BreakdownNode[] {
  const cats = new Map<string, BreakdownNode>();
  for (const r of resources) {
    let cat = cats.get(r.service_category);
    if (!cat) {
      cat = { name: r.service_category, level: 1, cost: 0, pct_of_parent: 100, children: [] };
      cats.set(r.service_category, cat);
    }
    cat.cost += r.cost;
    let svc = cat.children.find((c) => c.name === r.service_name);
    if (!svc) {
      svc = { name: r.service_name, level: 2, cost: 0, pct_of_parent: 0, children: [] };
      cat.children.push(svc);
    }
    svc.cost += r.cost;
    let rt = svc.children.find((c) => c.name === r.resource_type);
    if (!rt) {
      rt = { name: r.resource_type || 'Other', level: 3, cost: 0, pct_of_parent: 0, children: [] };
      svc.children.push(rt);
    }
    rt.cost += r.cost;
    rt.children.push({
      name: `${r.resource_name} (${r.resource_group})`,
      level: 4,
      cost: r.cost,
      pct_of_parent: 0,
      children: [],
    });
  }

  const finalize = (nodes: BreakdownNode[], parentCost: number): BreakdownNode[] => {
    nodes.sort((a, b) => b.cost - a.cost);
    for (const n of nodes) {
      n.cost = round2(n.cost);
      n.pct_of_parent = parentCost ? round1((n.cost / parentCost) * 100) : 0;
      if (n.children.length) n.children = finalize(n.children, n.cost);
    }
    return nodes;
  };

  const total = [...cats.values()].reduce((s, c) => s + c.cost, 0);
  return finalize([...cats.values()], total);
}
