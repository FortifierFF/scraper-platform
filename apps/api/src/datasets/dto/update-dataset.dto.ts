import { IsString, IsOptional, IsArray, IsBoolean, IsObject } from 'class-validator';

export class UpdateDatasetDto {
  @IsOptional()
  @IsString()
  name?: string;

  @IsOptional()
  @IsString()
  entity_type?: string;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  tags?: string[];

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  sources?: string[];

  @IsOptional()
  @IsString()
  schedule_cron?: string;

  @IsOptional()
  @IsString()
  extractor?: string;

  @IsOptional()
  @IsObject()
  config?: Record<string, any>;

  @IsOptional()
  @IsBoolean()
  is_enabled?: boolean;
}
