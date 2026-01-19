import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
} from '@nestjs/common';
import { Inject } from '@nestjs/common';
import { Kysely } from 'kysely';
import { Database, Tenant } from '../db/schema';
import { DB } from '../db/db.module';

// Extend Express Request to include tenant
declare global {
  namespace Express {
    interface Request {
      tenant?: Tenant;
    }
  }
}

@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(@Inject(DB) private readonly db: Kysely<Database>) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const apiKey = request.headers['x-api-key'];

    if (!apiKey) {
      throw new UnauthorizedException('Missing X-API-Key header');
    }

    // Look up tenant by API key
    const tenant = await this.db
      .selectFrom('tenants')
      .selectAll()
      .where('api_key', '=', apiKey)
      .where('is_enabled', '=', true)
      .executeTakeFirst();

    if (!tenant) {
      throw new UnauthorizedException('Invalid or disabled API key');
    }

    // Attach tenant to request context
    request.tenant = tenant;
    return true;
  }
}
