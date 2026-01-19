import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Query,
  Body,
  Request,
} from '@nestjs/common';
import { DatasetsService } from './datasets.service';
import { CreateDatasetDto } from './dto/create-dataset.dto';
import { UpdateDatasetDto } from './dto/update-dataset.dto';
import { Tenant } from '../db/schema';

@Controller('v1/datasets')
export class DatasetsController {
  constructor(private readonly datasetsService: DatasetsService) {}

  @Get()
  async findAll(
    @Request() req: any,
    @Query('entityType') entityType?: string,
    @Query('tag') tag?: string,
    @Query('source') source?: string,
    @Query('mine') mineParam?: string,
  ) {
    const tenant: Tenant = req.tenant;
    const mine = mineParam === 'true' ? true : mineParam === 'false' ? false : undefined;
    return this.datasetsService.findAll(tenant, {
      entityType,
      tag,
      source,
      mine,
    });
  }

  @Get(':id')
  async findOne(@Request() req: any, @Param('id') id: string) {
    const tenant: Tenant = req.tenant;
    return this.datasetsService.findOne(id, tenant);
  }

  @Post()
  async create(@Request() req: any, @Body() dto: CreateDatasetDto) {
    const tenant: Tenant = req.tenant;
    return this.datasetsService.create(tenant, dto);
  }

  @Patch(':id')
  async update(
    @Request() req: any,
    @Param('id') id: string,
    @Body() dto: UpdateDatasetDto,
  ) {
    const tenant: Tenant = req.tenant;
    return this.datasetsService.update(id, tenant, dto);
  }
}
