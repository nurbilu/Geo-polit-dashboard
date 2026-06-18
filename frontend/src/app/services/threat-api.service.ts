import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  Alert,
  AlertFilters,
  DashboardSummary,
  Paginated,
} from '../models/alert.model';

@Injectable({ providedIn: 'root' })
export class ThreatApiService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getAlerts(filters: AlertFilters = {}, limit = 50): Observable<Paginated<Alert>> {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('ordering', '-published_at');

    if (filters.region) {
      params = params.set('region', filters.region);
    }
    if (filters.is_threat !== '' && filters.is_threat !== undefined) {
      params = params.set('is_threat', String(filters.is_threat));
    }
    if (filters.min_severity) {
      params = params.set('min_severity', String(filters.min_severity));
    }
    if (filters.has_image) {
      params = params.set('has_image', '1');
    }

    return this.http.get<Paginated<Alert>>(`${this.base}/alerts/`, { params });
  }

  getSummary(hours = 24): Observable<DashboardSummary> {
    const params = new HttpParams().set('hours', String(hours));
    return this.http.get<DashboardSummary>(`${this.base}/summary/`, { params });
  }
}
