import { IsString, IsUUID, IsOptional, IsIn } from 'class-validator';

export class CreateJobDto {
  @IsString()
  @IsUUID()
  datasetId: string;

  @IsOptional()
  @IsString()
  @IsIn(['quick_check', 'full'])
  mode?: 'quick_check' | 'full'; // 'quick_check' = only page 1, 'full' = all pages until existing article found
}
