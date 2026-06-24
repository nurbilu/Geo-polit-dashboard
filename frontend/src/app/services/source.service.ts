import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../environments/environment';
import { Paginated } from '../models/alert.model';
import { Source, SourceInput } from '../models/source.model';

@Injectable({ providedIn: 'root' })
export class SourceService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  list(): Observable<Source[]> {
    return this.http
      .get<Paginated<Source>>(`${this.base}/sources/`, {
        params: { limit: '200', ordering: 'name' },
      })
      .pipe(map((page) => page.results));
  }

  create(payload: SourceInput): Observable<Source> {
    return this.http.post<Source>(`${this.base}/sources/`, payload);
  }

  update(id: number, payload: Partial<SourceInput>): Observable<Source> {
    return this.http.patch<Source>(`${this.base}/sources/${id}/`, payload);
  }

  remove(id: number): Observable<void> {
    return this.http
      .delete<void>(`${this.base}/sources/${id}/`)
      .pipe(map(() => void 0));
  }
}
