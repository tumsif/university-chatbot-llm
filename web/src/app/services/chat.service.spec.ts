import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ChatService } from './chat.service';
import { API_BASE_URL } from '../lib/api-config';

describe('ChatService', () => {
  let service: ChatService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ChatService,
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });
    service = TestBed.inject(ChatService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should check health via /api', () => {
    service.checkSystemHealth();
    const req = httpMock.expectOne(`${API_BASE_URL}/health`);
    expect(req.request.method).toBe('GET');
    req.flush({
      status: 'healthy',
      backend: 'FastAPI',
      llm_connected: true,
      llm_message: 'OK',
      model_configured: 'llama3',
    });
    expect(service.systemStatus()).toBe('online');
  });
});
