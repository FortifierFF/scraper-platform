import { Controller, Get, Param, Query, Request } from '@nestjs/common';
import { ItemsService } from './items.service';
import { Tenant } from '../db/schema';

@Controller('v1/items')
export class ItemsController {
  constructor(private readonly itemsService: ItemsService) {}

  @Get()
  async findAll(
    @Request() req: any,
    @Query('datasetId') datasetId?: string,
    @Query('entityType') entityType?: string,
    @Query('tag') tag?: string,
    @Query('source') source?: string,
    @Query('since') since?: string,
    @Query('until') until?: string,
    @Query('limit') limit?: string,
    @Query('cursor') cursor?: string,
  ) {
    const tenant: Tenant = req.tenant;
    return this.itemsService.findAll(tenant, {
      datasetId,
      entityType,
      tag,
      source,
      since,
      until,
      limit: limit ? parseInt(limit, 10) : undefined,
      cursor,
    });
  }

  @Get(':id')
  async findOne(@Request() req: any, @Param('id') id: string) {
    const tenant: Tenant = req.tenant;
    return this.itemsService.findOne(id, tenant);
  }
}
