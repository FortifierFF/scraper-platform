import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  Body,
  Request,
} from '@nestjs/common';
import { JobsService } from './jobs.service';
import { CreateJobDto } from './dto/create-job.dto';
import { Tenant } from '../db/schema';

@Controller('v1/jobs')
export class JobsController {
  constructor(private readonly jobsService: JobsService) {}

  @Post()
  async create(@Request() req: any, @Body() dto: CreateJobDto) {
    const tenant: Tenant = req.tenant;
    return this.jobsService.create(tenant, dto.datasetId, dto.mode);
  }

  @Get(':id')
  async findOne(@Request() req: any, @Param('id') id: string) {
    const tenant: Tenant = req.tenant;
    return this.jobsService.findOne(id, tenant);
  }

  @Get()
  async findAll(
    @Request() req: any,
    @Query('datasetId') datasetId?: string,
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('cursor') cursor?: string,
  ) {
    const tenant: Tenant = req.tenant;
    return this.jobsService.findAll(tenant, {
      datasetId,
      status,
      limit: limit ? parseInt(limit, 10) : undefined,
      cursor,
    });
  }
}
