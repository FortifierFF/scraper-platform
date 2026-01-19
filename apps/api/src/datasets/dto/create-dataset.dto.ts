import { IsString, IsOptional, IsArray, IsBoolean, IsObject, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';

export class CreateDatasetDto {
  @IsString()
  name: string;

  @IsString()
  entity_type: string;

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

  @IsString()
  extractor: string;

  @IsObject()
  config: Record<string, any>;

  @IsOptional()
  @IsBoolean()
  is_enabled?: boolean;
}
