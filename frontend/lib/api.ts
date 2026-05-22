const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export interface Post {
  id: number;
  linkedin_url: string;
  title: string | null;
  subtitle: string | null;
  content: string | null;
  summary: string | null;
  quote: string | null;
  mariana_take: string | null;
  content_type: string | null;
  difficulty: string | null;
  post_date: string | null;
  tags: string[];
  school_name: string | null;
  discipline_name: string | null;
}

export interface PostList {
  items: Post[];
  total: number;
  page: number;
}

export interface PostDetail {
  post: Post;
  related: Post[];
}

export interface Discipline {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  school_name: string | null;
  post_count: number;
  lesson_count: number;
  lab_count: number;
}

export interface School {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  disciplines: Discipline[];
}

export interface GraphNode {
  id: number;
  label: string;
  x: number;
  y: number;
  radius: number;
  color: string;
  layer: number;
  posts: number;
  is_new: boolean;
  is_trending: boolean;
}

export interface GraphEdge {
  source: number;
  target: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SearchResult {
  type: string;
  title: string;
  subtitle: string | null;
  tags: string[];
  url: string;
}

export interface SearchResults {
  results: SearchResult[];
  total: number;
}

export interface RawPost {
  id: number;
  linkedin_url: string;
  raw_json: unknown;
  created_at: string | null;
}

export interface Stats {
  total_posts: number;
  total_disciplines: number;
  total_schools: number;
  total_labs: number;
}

export const api = {
  posts: {
    list: (page = 1, perPage = 20, disciplineId?: number) =>
      fetchAPI<PostList>(`/api/posts?page=${page}&per_page=${perPage}${disciplineId ? `&discipline_id=${disciplineId}` : ''}`),
    get: (id: number) => fetchAPI<PostDetail>(`/api/posts/${id}`),
    trending: () => fetchAPI<Post[]>(`/api/posts/trending`),
    recent: () => fetchAPI<Post[]>(`/api/posts/recent`),
  },
  disciplines: {
    list: () => fetchAPI<Discipline[]>(`/api/disciplines`),
    schools: () => fetchAPI<School[]>(`/api/disciplines/schools`),
    get: (id: number) => fetchAPI<Discipline>(`/api/disciplines/${id}`),
  },
  search: {
    query: (q: string) => fetchAPI<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`),
  },
  graph: {
    get: () => fetchAPI<GraphData>(`/api/graph/`),
    discipline: (id: number) => fetchAPI<GraphData>(`/api/graph/discipline/${id}`),
  },
  about: {
    get: () => fetchAPI<{name: string; url: string}>('/api/about'),
  },
  stats: {
    get: () => fetchAPI<Stats>(`/api/stats/`),
  },
  rawPosts: {
    list: () => fetchAPI<RawPost[]>('/api/raw-posts'),
  },
  sync: {
    trigger: () => fetchAPI<{task_id: string}>('/api/sync', { method: 'POST' }),
    status: (taskId: string) => fetchAPI<{task_id: string; status: string; messages: any[]}>(`/api/sync/${taskId}`),
    stream: (taskId: string) => {
      const base = API_BASE || '';
      return new EventSource(`${base}/api/sync/stream/${taskId}`);
    },
  },
};
